# 눈누 official_url 전수 스캔 결과 (dev) - 2026-07-29

- 실행: `noonnu-url-scan --target dev` (읽기 전용, PR #151 도구 + 후속 수정 반영판)
- 리포트: `apps/pipeline/output/noonnu-url-scan-report.json` (미추적, 상태 파일과 세트)
- 관련: #148, #150, PR #151

## 요약 (1,110종 전수, 오류 0)

```
classification : match 925 / mismatch 184 / no_link 1
action         : keep 925 / manual_review 182 / auto_fix_safe 2 / nullify(보류) 1
오염(양필드 동일): noonnu_account 172 / third_party_social 1 / 나머지 정상 937
no_container   : 0건 (페이지 구조 가정 100% 성립, 5% 임계 무관)
재시도 잔여     : 0건, exit 0
```

dev 오염 172종은 prod 실측 172종과 수치가 일치한다. 172 = manual_review 169 + auto_fix_safe 2 + no_link(보류) 1.

## 핵심 발견: 재추출 값이 32개 호스트로 수렴한다

오염 169건(manual_review)의 재추출 호스트 분포. 앵커 근거("다운로드 페이지로 이동" 계열)는 169/169 전부 보유하며, `auto_fix_safe`로 못 간 이유는 한글 제작사명이 영문 도메인과 문자열 매칭될 수 없어서다(AND 조건). 제작사명과 도메인의 의미 대응은 표에서 보듯 강하다.

| 호스트 | 건수 | 제작사 예시 | slug 예시 |
|---|---|---|---|
| clova.ai | 109 | 네이버 | 힘내라는-말보단, 따뜻한-작별 |
| www.ssro.net | 12 | 스스로넷 | 나는야핵인싸체-최서연, 칠백삼체-유서연 |
| www.kopus.org | 6 | 한국출판인회의 | kopub-world-바탕, kopub-바탕-2.0 |
| freesentation.blog | 3 | 오토노머스에이투지 X 이주임, 이주임, 이주임 X 김도균 | 에이투지체, 프리젠테이션 |
| 416foundation.org | 3 | 4・16재단 | 사월십육일체-약속, 사월십육일체-안전 |
| elice.io | 3 | 엘리스 | 엘리스-dx널리체, 엘리스디지털배움체 |
| quiple.dev | 2 | Lee Minseo, 이민서 | 마루미냐-한글, 전기칩-한글 |
| nelna.shop | 2 | (주)낼나 | 낼나-예샘체, 낼나-리지체 |
| flightsans.jejuair.net | 2 | 제주항공 | 플라이트-산스, 플라이트-산스-title |
| goorm-sans.goorm.io | 2 | 구름 | 구름-산스, 구름-산스-코드 |
| trend.mangoboard.net | 2 | (주)리아모어소프트 | 망고보드-별별체, 망고보드-또박체 |
| toss.im | 2 | (주)비바리퍼블리카 | 머니그라피-픽셀, 머니그라피-라운디드 |
| sun.fo | 2 | SUNN YOUN | 스위트, 수트 |
| www.dongguk.edu | 1 | 동국대학교 | 동국체 |
| www.adoba.net | 1 | 아도바 주식회사 | 아도바-온리체 |
| gwangjuro.net | 1 | 지역공공정책플랫폼광주로 | 박용준투사회보체 |
| www.bookend.tech | 1 | (주)북엔드 | 북엔드-바탕 |
| hbios.quiple.dev | 1 | 이민서 | hbios-sys |
| seed.line.me | 1 | 라인 | line-seed |
| yafitmove.notion.site | 1 | Yanadoo Corp. | move-sans |
| hcroh.org | 1 | 노회찬재단 | 노회찬체 |
| gamwulchi.associates | 1 | 가물치들 | 가물치-무료고딕 |
| www.kita.net | 1 | 한국무역협회 | kita |
| blog.howeverina.studio | 1 | 그리운 X 연이나 | 그리운-연이나-둥둥 |
| jinseong-kim.notion.site | 1 | 김진성 | 민산스 |
| i-eumcreative.org | 1 | 엉뚱상상 | tiquitaca |
| supernovice.org | 1 | 김양진 | 양진체 |
| www.kofih.org | 1 | 한국국제보건의료재단 | kofih이종욱체 |
| tdtd.io | 1 | (주)와이즈폰트 | 타닥타닥체 |
| hagibrew.oopy.io | 1 | 이근학 | 문래양조-영철체 |
| webtoon.daum.net | 1 | 산돌X윤태호 | 미생체 |
| oddatelier.net | 1 | OA 엔터테인먼트 주식회사 | zen-serif |

호스트 종수: 32

개별 169건 검수 대신 **호스트 32개 검수**로 좁힐 수 있다는 뜻이다. clova.ai 하나가 109건(네이버 클로바 손글씨 캠페인)을 해소한다.

## 비오염 mismatch 12건 (드리프트)

- typedia.kr(경쟁 아카이브) → 제작사 페이지 5건: #148과 같은 "아카이브를 출처로 기록" 계열
- github LICENSE 파일 링크 → 프로젝트 페이지 5건(갈무리 시리즈, interop): 기존 값도 라이선스 근거로는 유효할 수 있어 사람 판단 필요
- `아임크리수진체`: 기존 imcrefont.com이 재추출값(구글 드라이브 폴더)보다 더 공식적 — **재추출 값이 항상 정답이 아니라는 실증.** 호스트 검수에서 drive.google.com이 자연 배제됨

## 특수 케이스

- `밍기적체`: official_url이 유튜브 영상 → third_party_social, manual_review
- `google-sans-flex`: 본문에 외부 링크 없음 → nullify 권고이나 official_url NOT NULL 제약으로 보류 목록 (0027 결정 대기)

## 다음 결정 (사용자)

정정 방식 선택지: (A) 호스트 단위 승인 — 32개 표를 검토해 승인 호스트를 정하면 해당 건을 manifest로 일괄 정정 (B) 169건 개별 검수 (C) 판정 로직에 도메인 지식 추가 후 재스캔.

## 재현

```
cd apps/pipeline && uv run python -m fontagit_pipeline noonnu-url-scan --target dev \
  --state output/noonnu-url-scan-state.jsonl --out output/noonnu-url-scan-report.json
```
