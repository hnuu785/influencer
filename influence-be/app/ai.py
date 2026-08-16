from __future__ import annotations

import base64
import re
from pathlib import Path

from openai import AsyncOpenAI

from app.config import Settings
from app.schemas import (
    ContentBriefSchema,
    GeneratedPackage,
    GeneratedQualityIssue,
    PackageGenerationResult,
    QualityBatch,
    StoryboardBeat,
    StoryCardBatch,
    StoryCardCandidate,
)


STORY_SYSTEM_PROMPT = """
당신은 한국어 퍼스널 브랜딩 편집자다.
사용자의 실제 기록만 근거로 최대 3개의 StoryCard 후보를 만든다.
기록에 없는 사실·성과·감정을 추가하지 않는다.
각 후보는 서로 다른 콘텐츠 각도를 가져야 하고 source_excerpt는 입력에서 짧게 발췌한다.
""".strip()

PACKAGE_SYSTEM_PROMPT = """
당신은 Instagram 콘텐츠 제작 기획자다.
승인된 StoryCard, 사용자 브랜드 프로필, 개인 승인 이력, 권리 확인 포맷 패턴을 바탕으로
Reel, Carousel, Story 제작 패키지를 정확히 하나씩 만든다.
최종 미디어를 만들지 말고 제작자가 바로 실행할 Storyboard, 대사·카피, 자막, CTA,
장면·슬라이드·프레임 지시를 한국어로 제공한다.
Reel은 15~45초, 기본 목표 25초다.
원문에 없는 사실을 추가하거나 레퍼런스 문장을 복제하지 않는다.
""".strip()

QUALITY_SYSTEM_PROMPT = """
당신은 콘텐츠 품질 검수자다.
사용자 원문과 제작 패키지를 비교하여 다음 문제만 구조화한다:
1) 원문에 없는 사실·성과·감정, 2) 개인정보·민감정보, 3) 레퍼런스와 과도한 유사성.
숫자 점수를 만들지 않는다. 문제가 없으면 issues를 빈 배열로 반환한다.
""".strip()

EMAIL_PATTERN = re.compile(
    r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9])",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(r"(?<!\d)01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)")


def minimize_personal_data(text: str) -> str:
    minimized = EMAIL_PATTERN.sub("[이메일 제거됨]", text)
    return PHONE_PATTERN.sub("[전화번호 제거됨]", minimized)


class DemoAIProvider:
    mode = "demo"
    generation_model = "deterministic-demo"
    review_model = "deterministic-demo"

    async def transcribe(self, path: Path) -> str:
        return (
            f"{path.name} 음성 기록이 추가되었습니다. "
            "개발 모드에서는 중요한 내용을 텍스트 답변으로 보완해 주세요."
        )

    async def describe_image(self, path: Path, content_type: str) -> str:
        del content_type
        return f"{path.name} 이미지가 기록에 포함되었습니다."

    async def embed(self, text: str) -> list[float] | None:
        return None

    async def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        return [None for _ in texts]

    async def create_story_cards(self, context: str) -> StoryCardBatch:
        compact = " ".join(context.split())
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?。])\s+|\n+", compact)
            if part.strip()
        ]
        seed = sentences[0] if sentences else "오늘의 기록"
        evidence = seed[:220]
        cards = [
            StoryCardCandidate(
                event=seed[:120],
                observation="직접 해보니 예상과 결과 사이에 차이가 있었다.",
                emotion="의외였다",
                opinion="결과보다 그 과정에서 바뀐 판단을 기록할 가치가 있다.",
                content_angles=["경험 회고", "실무 인사이트"],
                source_excerpt=evidence,
            ),
            StoryCardCandidate(
                event=seed[:120],
                observation="작은 실험이 다음 선택의 기준을 더 분명하게 만들었다.",
                emotion="확신이 생겼다",
                opinion="완성된 답보다 실제로 시도하며 얻은 기준이 더 유용하다.",
                content_angles=["빌드 인 퍼블릭", "배운 점"],
                source_excerpt=evidence,
            ),
            StoryCardCandidate(
                event=seed[:120],
                observation="다른 사람도 같은 상황에서 고민할 만한 질문이 보였다.",
                emotion="공유하고 싶었다",
                opinion="개인 경험을 질문으로 열어두면 더 좋은 대화를 시작할 수 있다.",
                content_angles=["질문형 콘텐츠", "커뮤니티 대화"],
                source_excerpt=evidence,
            ),
        ]
        return StoryCardBatch(cards=cards)

    async def create_packages(
        self,
        story: StoryCardCandidate,
        profile: dict,
        personal_context: list[str],
        patterns: list[dict],
    ) -> PackageGenerationResult:
        audience = profile.get("audience") or "AI·테크에 관심 있는 실무자"
        core = story.opinion
        brief = ContentBriefSchema(
            audience=audience,
            objective="실제 경험에 기반한 전문성과 꾸준한 게시",
            core_message=core,
            proof_points=[story.observation, story.source_excerpt],
            constraints=["개인 경험을 일반적 성능 주장으로 확대하지 않음"],
        )
        reel = GeneratedPackage(
            format="reel",
            objective="discovery",
            hook_options=[
                f"결과보다 먼저 바뀐 건 제 판단이었습니다.",
                f"직접 해보고 나서야 알게 된 한 가지.",
                f"같은 상황을 다르게 보게 된 이유입니다.",
            ],
            storyboard=[
                StoryboardBeat(
                    order=1,
                    label="훅",
                    timing="0~2초",
                    visual="카메라 정면 또는 가장 강한 결과 화면",
                    content="직접 해보고 나서야 알게 된 한 가지.",
                    production_note="첫 문장을 화면 중앙 큰 자막으로 표시",
                ),
                StoryboardBeat(
                    order=2,
                    label="상황",
                    timing="2~7초",
                    visual="기록에 포함된 작업 화면이나 사진",
                    content=story.event,
                    production_note="원본 장면을 1~2개만 사용",
                ),
                StoryboardBeat(
                    order=3,
                    label="관찰",
                    timing="7~18초",
                    visual="전후 또는 과정 화면",
                    content=story.observation,
                    production_note="핵심 변화에 밑줄 자막",
                ),
                StoryboardBeat(
                    order=4,
                    label="배움·CTA",
                    timing="18~25초",
                    visual="다시 카메라 정면",
                    content=f"{core} 여러분은 어떤 기준으로 판단하시나요?",
                    production_note="마지막 질문 뒤 1초 여백",
                ),
            ],
            script_or_copy=[story.event, story.observation, core],
            captions=["직접 해보고 알게 된 것", story.observation, core],
            cta="여러분은 어떤 기준으로 판단하시나요?",
            production_instructions=[
                "세로 9:16, 25초 목표",
                "원본 장면은 2개 이하로 사용",
                "자막은 한 화면 두 줄 이하",
            ],
        )
        carousel = GeneratedPackage(
            format="carousel",
            objective="save_and_share",
            hook_options=["직접 해보고 바뀐 생각", "결과를 바꾼 작은 차이", "다음 실험 전 볼 체크리스트"],
            storyboard=[
                StoryboardBeat(
                    order=1,
                    label="표지",
                    timing="1장",
                    visual="여백이 큰 제목 카드",
                    content="직접 해보고 바뀐 생각",
                    production_note="12자 안팎의 큰 제목",
                ),
                StoryboardBeat(
                    order=2,
                    label="상황",
                    timing="2장",
                    visual="원본 사진 또는 간단한 도식",
                    content=story.event,
                    production_note="사실만 짧게 정리",
                ),
                StoryboardBeat(
                    order=3,
                    label="발견",
                    timing="3~4장",
                    visual="전후 비교 레이아웃",
                    content=story.observation,
                    production_note="관찰과 해석을 분리",
                ),
                StoryboardBeat(
                    order=4,
                    label="정리",
                    timing="5~6장",
                    visual="체크리스트와 질문",
                    content=core,
                    production_note="저장할 이유가 되는 한 줄 요약",
                ),
            ],
            script_or_copy=[
                "직접 해보고 바뀐 생각",
                story.event,
                story.observation,
                core,
            ],
            captions=[f"{story.event}\n\n{story.observation}\n\n{core}"],
            cta="다음 실험 전에 저장해 두세요.",
            production_instructions=[
                "4:5 비율, 6장 기본",
                "슬라이드당 핵심 문장 하나",
                "원문 근거와 개인 의견의 시각 스타일을 구분",
            ],
        )
        story_package = GeneratedPackage(
            format="story",
            objective="relationship",
            hook_options=["여러분이라면?", "직접 해보니 달랐어요", "둘 중 무엇이 더 중요할까요?"],
            storyboard=[
                StoryboardBeat(
                    order=1,
                    label="상황",
                    timing="1프레임",
                    visual="원본 사진 위 짧은 문장",
                    content=story.event,
                    production_note="배경을 어둡게 처리해 가독성 확보",
                ),
                StoryboardBeat(
                    order=2,
                    label="투표",
                    timing="2프레임",
                    visual="양자택일 투표 스티커",
                    content="여러분이라면 결과와 과정 중 무엇을 먼저 보나요?",
                    production_note="투표 선택지는 8자 이하",
                ),
                StoryboardBeat(
                    order=3,
                    label="내 관점",
                    timing="3프레임",
                    visual="말풍선 카드",
                    content=core,
                    production_note="개인 경험임을 표시",
                ),
            ],
            script_or_copy=[story.event, "여러분이라면?", core],
            captions=[],
            cta="투표하고 이유를 답장으로 알려주세요.",
            production_instructions=[
                "9:16, 3프레임",
                "Instagram 기본 투표 스티커 사용",
                "마지막 프레임에 답장 유도",
            ],
        )
        return PackageGenerationResult(
            brief=brief, packages=[reel, carousel, story_package]
        )

    async def review(
        self,
        source_text: str,
        packages: list[GeneratedPackage],
        reference_guidance: list[str],
    ) -> QualityBatch:
        issues: list[GeneratedQualityIssue] = []
        email_match = EMAIL_PATTERN.search(source_text)
        phone_match = PHONE_PATTERN.search(source_text)
        private_value = email_match.group(0) if email_match else (
            phone_match.group(0) if phone_match else None
        )
        if private_value:
            for package in packages:
                issues.append(
                    GeneratedQualityIssue(
                        format=package.format,
                        category="privacy",
                        severity="high",
                        target_ref=private_value,
                        source_ref="사용자 원문",
                        message="공개 전 개인정보를 제거하거나 사용 여부를 확인해 주세요.",
                    )
                )
        return QualityBatch(issues=issues)


class OpenAIProvider:
    mode = "openai"

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.transcribe_model = settings.openai_transcribe_model
        self.embedding_model = settings.openai_embedding_model
        self.generation_model = settings.openai_generation_model
        self.review_model = settings.openai_review_model

    async def transcribe(self, path: Path) -> str:
        with path.open("rb") as audio_file:
            result = await self.client.audio.transcriptions.create(
                model=self.transcribe_model,
                file=audio_file,
                language="ko",
            )
        return result.text

    async def describe_image(self, path: Path, content_type: str) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode()
        response = await self.client.responses.create(
            model=self.generation_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "이 이미지를 한국어로 간결하게 설명하고, "
                                "콘텐츠 소재가 될 수 있는 관찰만 적어라. "
                                "신원이나 확인할 수 없는 사실은 추측하지 마라."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{content_type};base64,{encoded}"
                            ),
                        },
                    ],
                }
            ],
            store=False,
        )
        return response.output_text

    async def embed(self, text: str) -> list[float] | None:
        embeddings = await self.embed_many([text])
        return embeddings[0]

    async def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=[minimize_personal_data(text) for text in texts],
            dimensions=1536,
        )
        by_index = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in by_index]

    async def create_story_cards(self, context: str) -> StoryCardBatch:
        response = await self.client.responses.parse(
            model=self.review_model,
            input=[
                {"role": "system", "content": STORY_SYSTEM_PROMPT},
                {"role": "user", "content": minimize_personal_data(context)},
            ],
            text_format=StoryCardBatch,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError("StoryCard structured output was empty")
        return response.output_parsed

    async def create_packages(
        self,
        story: StoryCardCandidate,
        profile: dict,
        personal_context: list[str],
        patterns: list[dict],
    ) -> PackageGenerationResult:
        payload = {
            "story": story.model_dump(),
            "brand_profile": profile,
            "approved_personal_context": personal_context,
            "rights_checked_patterns": patterns,
        }
        response = await self.client.responses.parse(
            model=self.review_model,
            input=[
                {"role": "system", "content": PACKAGE_SYSTEM_PROMPT},
                {"role": "user", "content": minimize_personal_data(str(payload))},
            ],
            text_format=PackageGenerationResult,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError("Content package structured output was empty")
        formats = {package.format for package in response.output_parsed.packages}
        if formats != {"reel", "carousel", "story"}:
            raise RuntimeError("Content package output must contain all three formats")
        return response.output_parsed

    async def review(
        self,
        source_text: str,
        packages: list[GeneratedPackage],
        reference_guidance: list[str],
    ) -> QualityBatch:
        response = await self.client.responses.parse(
            model=self.review_model,
            input=[
                {"role": "system", "content": QUALITY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": minimize_personal_data(
                        str({
                            "source": minimize_personal_data(source_text),
                            "packages": [
                                package.model_dump() for package in packages
                            ],
                            "reference_guidance": reference_guidance,
                        })
                    ),
                },
            ],
            text_format=QualityBatch,
            store=False,
        )
        if response.output_parsed is None:
            raise RuntimeError("Quality review structured output was empty")
        return response.output_parsed


def create_ai_provider(settings: Settings):
    if settings.openai_api_key:
        return OpenAIProvider(settings)
    return DemoAIProvider()
