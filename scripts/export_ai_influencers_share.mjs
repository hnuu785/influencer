#!/usr/bin/env node

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "..");
const datasetDate = "2026-08-16";
const outputDirectory = resolve(
  process.argv[2] ??
    resolve(projectRoot, "outputs", `ai-influencer-dataset-${datasetDate}`),
);

const sourceFiles = [
  resolve(
    projectRoot,
    "influence-be/data/ai_virtual_influencers_2026-08-16.json",
  ),
  resolve(
    projectRoot,
    "influence-be/data/ai_virtual_influencers_expanded_2026-08-16.json",
  ),
];

const sourceRecords = (
  await Promise.all(
    sourceFiles.map(async (path) => JSON.parse(await readFile(path, "utf8"))),
  )
).flat();

const usernames = new Set();
for (const record of sourceRecords) {
  const username = record.username.trim().replace(/^@/, "").toLowerCase();
  if (usernames.has(username)) {
    throw new Error(`Duplicate username: ${username}`);
  }
  if (!record.source_url || !record.observed_at || !record.confidence) {
    throw new Error(`Missing provenance for: ${username}`);
  }
  usernames.add(username);
}

if (sourceRecords.length !== 58) {
  throw new Error(`Expected 58 records, received ${sourceRecords.length}`);
}

const records = sourceRecords
  .map((record) => {
    const username = record.username.trim().replace(/^@/, "").toLowerCase();
    return {
      platform: "instagram",
      username,
      profile_url: `https://www.instagram.com/${username}/`,
      full_name: record.full_name,
      follower_count: record.follower_count ?? null,
      following_count: record.following_count ?? null,
      media_count: record.media_count ?? null,
      engagement_rate_percent: record.engagement_rate_percent ?? null,
      category: record.category ?? null,
      profile_type: record.profile_type ?? null,
      country: record.country ?? null,
      creator_or_manager: record.creator_or_manager ?? null,
      observed_at: record.observed_at,
      confidence: record.confidence,
      account_status: record.account_status ?? "active_or_unconfirmed",
      source_url: record.source_url,
      secondary_source_urls: record.secondary_source_urls ?? [],
      source_rank: record.source_rank ?? null,
      follower_growth_3mo_percent: record.follower_growth_3mo_percent ?? null,
    };
  })
  .sort(
    (left, right) =>
      (right.follower_count ?? -1) - (left.follower_count ?? -1) ||
      left.username.localeCompare(right.username),
  )
  .map((record, index) => ({ rank_by_follower_snapshot: index + 1, ...record }));

const confidenceCounts = Object.fromEntries(
  ["high", "medium", "stale"].map((confidence) => [
    confidence,
    records.filter((record) => record.confidence === confidence).length,
  ]),
);

const dataset = {
  dataset_name: "AI Instagram Influencers — Public Profile Snapshots",
  dataset_version: datasetDate,
  generated_at: new Date().toISOString(),
  language: "ko",
  license_note:
    "각 행의 source_url 원문 조건과 Instagram 플랫폼 정책을 확인한 뒤 사용하세요.",
  scope: {
    record_count: records.length,
    confidence_counts: confidenceCounts,
    includes:
      "공개 출처에서 확인한 AI·CGI·애니메이션·브랜드 가상 Instagram 계정의 프로필 지표 스냅샷",
    excludes:
      "이메일, 전화번호, 비공개 정보, 게시물 본문, 이미지, 영상, 댓글",
    freshness_note:
      "팔로워·팔로잉·게시물·참여율은 실시간 값이 아니라 observed_at 시점 또는 출처가 제시한 스냅샷입니다.",
    direct_instagram_fetch: false,
  },
  confidence_definition: {
    high: "2026년 7~8월 자료를 포함해 복수 또는 비교적 최신 공개 출처로 교차 확인",
    medium: "2026년 공개 순위·벤치마크의 단일 출처 중심",
    stale: "과거 수치이거나 현재 비활성 가능성이 있어 사용 전 재확인 필요",
  },
  fields: {
    rank_by_follower_snapshot: "팔로워 스냅샷 내림차순 순위",
    platform: "소셜 플랫폼",
    username: "Instagram 사용자명(@ 제외)",
    profile_url: "정규화한 공개 Instagram 프로필 URL",
    full_name: "표시 이름",
    follower_count: "출처 관측 시점의 팔로워 수",
    following_count: "출처 관측 시점의 팔로잉 수",
    media_count: "출처 관측 시점의 게시물 수",
    engagement_rate_percent: "참여율의 퍼센트 단위 숫자(예: 1.25는 1.25%)",
    category: "콘텐츠 또는 계정 분야",
    profile_type: "가상 인물·캐릭터 유형",
    country: "관련 국가 또는 시장",
    creator_or_manager: "공개적으로 알려진 제작·운영 주체",
    observed_at: "출처가 지표를 관측한 날짜·월 또는 상태 설명",
    confidence: "출처 최신성과 교차 확인 수준",
    account_status: "활성 상태 메모",
    source_url: "주 출처 URL",
    secondary_source_urls: "교차 확인용 추가 출처 URL 배열",
    source_rank: "해당 출처 내 순위(제공된 경우)",
    follower_growth_3mo_percent: "3개월 팔로워 성장률 퍼센트 단위 숫자(제공된 경우)",
  },
  records,
};

const readme = `# AI Instagram Influencers 공유 데이터셋

- 기준일: ${datasetDate}
- 레코드: ${records.length}개
- 신뢰도: high ${confidenceCounts.high} / medium ${confidenceCounts.medium} / stale ${confidenceCounts.stale}
- 문자 인코딩: UTF-8

## 파일

- \`AI_Instagram_Influencers_58_${datasetDate}.json\`: 메타데이터, 필드 설명, 58개 레코드를 포함한 단일 JSON
- \`MANIFEST.json\`: 파일 크기와 SHA-256 체크섬

## 사용 주의

팔로워·팔로잉·게시물·참여율은 실시간 Instagram 값이 아니라 각 공개 출처의 관측 시점 스냅샷입니다. \`observed_at\`, \`confidence\`, \`source_url\`을 함께 사용하세요. \`stale\` 레코드는 순위나 캠페인 판단 전에 재확인이 필요합니다.

이 묶음에는 이메일, 전화번호, 비공개 정보, 게시물 본문, 이미지, 영상, 댓글이 포함되지 않습니다. 원문 재사용 또는 상업적 활용 전에는 각 출처의 이용 조건과 플랫폼 정책을 확인하세요.
`;

await mkdir(outputDirectory, { recursive: true });

const datasetFilename = `AI_Instagram_Influencers_58_${datasetDate}.json`;
const datasetBytes = Buffer.from(`${JSON.stringify(dataset, null, 2)}\n`, "utf8");
const readmeBytes = Buffer.from(readme, "utf8");

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const manifest = {
  dataset_version: datasetDate,
  generated_at: dataset.generated_at,
  record_count: records.length,
  files: [
    {
      name: datasetFilename,
      bytes: datasetBytes.length,
      sha256: sha256(datasetBytes),
    },
    {
      name: "README.md",
      bytes: readmeBytes.length,
      sha256: sha256(readmeBytes),
    },
  ],
};

await Promise.all([
  writeFile(resolve(outputDirectory, datasetFilename), datasetBytes),
  writeFile(resolve(outputDirectory, "README.md"), readmeBytes),
  writeFile(
    resolve(outputDirectory, "MANIFEST.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    "utf8",
  ),
]);

console.log(
  JSON.stringify(
    {
      output_directory: outputDirectory,
      dataset_file: resolve(outputDirectory, datasetFilename),
      record_count: records.length,
      confidence_counts: confidenceCounts,
    },
    null,
    2,
  ),
);
