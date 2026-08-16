import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.ai import minimize_personal_data
from app.config import Settings
from app.main import create_app
from app.storage import PreparedUpload


def make_mvp_client(tmp_path, *, storage=None) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    settings = Settings(
        redis_url=None,
        storage_dir=str(tmp_path),
        cors_origins=("http://localhost:3001",),
    )
    return TestClient(
        create_app(
            settings,
            engine=engine,
            storage=storage,
            initialize_schema=True,
        )
    )


class FakeS3Storage:
    mode = "s3"
    presign_ttl_seconds = 300

    def __init__(self):
        self.stored_references = []

    async def prepare_upload(self, user_id, filename, content_type):
        return PreparedUpload(
            key=f"pending/{user_id}/prepared.png",
            url="https://example-bucket.s3.ap-northeast-2.amazonaws.com/prepared.png",
            headers={"Content-Type": content_type},
        )

    async def materialize_pending(
        self, key, expected_size, expected_content_type, directory
    ):
        assert key.endswith("prepared.png")
        assert expected_content_type == "image/png"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "downloaded.png"
        target.write_bytes(b"test-image")
        assert expected_size == target.stat().st_size
        return target, target.stat().st_size

    async def store_record_file(
        self,
        path,
        user_id,
        record_id,
        content_type,
        *,
        pending_key=None,
    ):
        assert Path(path).exists()
        assert pending_key and pending_key.startswith(f"pending/{user_id}/")
        reference = f"s3://test-bucket/records/{user_id}/{record_id}/photo.png"
        self.stored_references.append(reference)
        return reference

    async def delete(self, reference):
        if reference in self.stored_references:
            self.stored_references.remove(reference)

    async def materialize(self, reference, directory):
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "photo.png"
        target.write_bytes(b"test-image")
        return target


def login(client: TestClient) -> None:
    invite = client.post(
        "/api/access/invite", json={"code": "STORYLOG-BETA"}
    )
    assert invite.status_code == 200
    token = invite.json()["invite_token"]
    response = client.post(
        "/api/auth/development", json={"invite_token": token}
    )
    assert response.status_code == 200


def create_story_cards(client: TestClient, text: str):
    events = client.get("/api/calendar/events")
    assert events.status_code == 200
    record = client.post(
        "/api/records",
        data={
            "text": text,
            "calendar_context_json": json.dumps([events.json()[0]]),
            "rights_confirmed": "true",
        },
    )
    assert record.status_code == 200
    record_id = record.json()["id"]
    questions = client.get(f"/api/records/{record_id}/questions").json()
    cards = client.post(
        f"/api/records/{record_id}/answers",
        json={
            "answers": [
                {
                    "question": questions[0]["text"],
                    "answer_type": "text",
                    "answer_text": "같은 모델인데 질문 순서를 바꾸자 답이 더 구체적이었다.",
                    "visibility": "public_ok",
                }
            ],
            "profile": {
                "topics": ["AI", "제품"],
                "audience": "AI 도구를 쓰는 제품 실무자",
                "tone": "담백하고 구체적으로",
                "taboo_topics": ["과장"],
            },
        },
    )
    assert cards.status_code == 200
    return record_id, cards.json()


def test_invite_code_is_required(tmp_path):
    with make_mvp_client(tmp_path) as client:
        response = client.post("/api/access/invite", json={"code": "WRONG"})

    assert response.status_code == 403


def test_mvp_flow_generates_three_format_packages_and_export(tmp_path):
    with make_mvp_client(tmp_path) as client:
        login(client)
        record_id, cards = create_story_cards(
            client,
            "오늘 AI 음성 에이전트를 테스트했는데 모델보다 질문 순서가 중요했다.",
        )
        response = client.post(
            f"/api/records/{record_id}/story-cards/{cards[0]['id']}/decision",
            json={"action": "approve"},
        )
        assert response.status_code == 200
        packages = response.json()
        assert [package["format"] for package in packages] == [
            "reel",
            "carousel",
            "story",
        ]
        assert all(package["storyboard"] for package in packages)

        for package in packages:
            approved = client.post(
                f"/api/packages/{package['id']}/decision",
                json={"action": "approve"},
            )
            assert approved.status_code == 200

        exported = client.post(
            f"/api/records/{record_id}/export",
            json={"package_ids": [package["id"] for package in packages]},
        )
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/zip"
        assert exported.content.startswith(b"PK")

        publication = client.post(
            f"/api/records/{record_id}/publication",
            json={
                "format": "reel",
                "published_url": "https://instagram.com/p/test",
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert publication.status_code == 200
        metrics = client.post(
            f"/api/publications/{publication.json()['id']}/metrics",
            json={
                "elapsed_hours": 24,
                "views": 100,
                "likes": 12,
                "comments": 3,
                "shares": 2,
                "saves": 8,
            },
        )
        assert metrics.status_code == 204


def test_unresolved_quality_warning_blocks_export(tmp_path):
    with make_mvp_client(tmp_path) as client:
        login(client)
        record_id, cards = create_story_cards(
            client,
            "오늘 테스트 연락처는 creator@example.com이고 질문 순서를 바꿨다.",
        )
        packages = client.post(
            f"/api/records/{record_id}/story-cards/{cards[0]['id']}/decision",
            json={"action": "approve"},
        ).json()
        reel = packages[0]
        assert reel["quality_issues"][0]["category"] == "privacy"
        client.post(
            f"/api/packages/{reel['id']}/decision", json={"action": "approve"}
        )

        blocked = client.post(
            f"/api/records/{record_id}/export",
            json={"package_ids": [reel["id"]]},
        )
        assert blocked.status_code == 409

        issue_id = reel["quality_issues"][0]["id"]
        resolved = client.post(
            f"/api/quality-issues/{issue_id}/resolve",
            json={"resolution": "acknowledged"},
        )
        assert resolved.status_code == 200

        exported = client.post(
            f"/api/records/{record_id}/export",
            json={"package_ids": [reel["id"]]},
        )
        assert exported.status_code == 200


def test_record_delete_removes_the_user_record(tmp_path):
    with make_mvp_client(tmp_path) as client:
        login(client)
        record_id, _ = create_story_cards(client, "삭제할 테스트 기록")

        deleted = client.delete(f"/api/records/{record_id}")
        missing = client.get(f"/api/records/{record_id}")

        assert deleted.status_code == 204
        assert missing.status_code == 404


def test_photo_can_be_combined_with_text_in_one_record(tmp_path):
    with make_mvp_client(tmp_path) as client:
        login(client)
        response = client.post(
            "/api/records",
            data={
                "text": "작업 화면을 보며 알게 된 점",
                "calendar_context_json": "[]",
                "rights_confirmed": "true",
            },
            files={"files": ("work.png", b"test-image", "image/png")},
        )

        assert response.status_code == 200
        assert {source["type"] for source in response.json()["sources"]} == {
            "text",
            "photo",
        }


def test_s3_photo_upload_is_prepared_and_attached_to_record(tmp_path):
    storage = FakeS3Storage()
    with make_mvp_client(tmp_path, storage=storage) as client:
        login(client)
        prepared = client.post(
            "/api/uploads/prepare",
            json={
                "files": [
                    {
                        "filename": "work.png",
                        "content_type": "image/png",
                        "size_bytes": len(b"test-image"),
                    }
                ]
            },
        )
        assert prepared.status_code == 200
        assert prepared.json()["mode"] == "s3"

        response = client.post(
            "/api/records",
            data={
                "text": "S3 사진 업로드 테스트",
                "calendar_context_json": "[]",
                "uploaded_files_json": json.dumps(
                    [prepared.json()["uploads"][0]["upload_token"]]
                ),
                "rights_confirmed": "true",
            },
        )

        assert response.status_code == 200
        assert response.json()["sources"][1]["filename"] == "work.png"
        assert storage.stored_references[0].startswith("s3://test-bucket/records/")
        deleted = client.delete(f"/api/records/{response.json()['id']}")
        assert deleted.status_code == 204
        assert storage.stored_references == []


def test_unsupported_photo_format_is_rejected_before_upload(tmp_path):
    with make_mvp_client(tmp_path) as client:
        login(client)
        response = client.post(
            "/api/uploads/prepare",
            json={
                "files": [
                    {
                        "filename": "iphone.heic",
                        "content_type": "image/heic",
                        "size_bytes": 100,
                    }
                ]
            },
        )

    assert response.status_code == 422
    assert "JPG" in response.json()["detail"]


def test_direct_identifiers_are_removed_before_model_context():
    minimized = minimize_personal_data(
        "creator@example.com 또는 010-1234-5678로 연락"
    )

    assert "creator@example.com" not in minimized
    assert "010-1234-5678" not in minimized
