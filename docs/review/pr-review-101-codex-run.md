### 종합 평가

- 전체 점수: 5.5/10
- 한줄 총평: 게이트 교정 방향은 맞지만, 조회 제한으로 불완전한 manifest를 조용히 만들 수 있어 현재 상태로는 위험합니다.
- 머지 권고: Must-fix 해결 전 불가

### 관점별 리뷰

| 관점 | 평가 | 핵심 |
|---|---|---|
| 정합성 | 보완 필요 | `source_key`가 항상 snapshot에서 파생된다는 설명과 코드가 다릅니다. |
| 영향도 | 위험 | 데이터가 1,000건을 넘으면 일부 finding/font가 누락될 수 있습니다. |
| SOLID/SRP | 양호 | build와 approve를 분리한 구조는 적절합니다. |
| 선제 위험 | 미흡 | 페이지네이션, 복수 snapshot, 기존 `source_key` 충돌 처리가 없습니다. |
| 방어적 입력 | 보완 필요 | 빈 검수자, `None` source key, 잘못된 DB 행을 충분히 막지 않습니다. |
| 보안 | 대체로 양호 | 시크릿 노출은 없지만 불필요한 `raw_text` 전체 조회는 줄여야 합니다. |
| Silent Failure | 위험 | 조회 제한으로 인한 일부 누락을 감지하지 못합니다. |
| 테스트 | 미흡 | 핵심 통합 테스트가 실제 헬퍼를 호출하지 않고 기존 테스트 하나는 무검증 상태가 됐습니다. |
| 스타일 | 보완 필요 | 테스트 파일 중간 import, 긴 쿼리 한 줄 등이 남아 있습니다. |
| 머피의 법칙 | 위험 | 전체 실행, 오래된 source key, 복수 snapshot 상황에서 잘못된 manifest가 나올 수 있습니다. |

### Critical - Must-fix (머지 차단)

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `audit_store.py:788-851` | Supabase 조회에 페이지네이션이 없어 manifest 일부가 조용히 누락될 수 있습니다. | `get_approved_findings`, `fonts`, `font_source_snapshots` 모두 `.select("*")...execute()` 한 번으로 끝납니다. 핸드오프에는 전체 폰트가 1,110개라고 적혀 있어 일반적인 1,000행 제한을 넘습니다. finding은 폰트당 tags/weights 두 건이면 더 많아집니다. | 안정적인 정렬과 `.range()`를 사용해 끝까지 조회하십시오. snapshot에서 `font_id`를 모은 뒤 fonts는 ID 기준으로 나눠 조회하고, 정확한 개수도 검증해야 합니다. 일부 조회라면 manifest 생성을 즉시 중단해야 합니다. |

### High - Should-fix

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `audit_store.py:845-871` | `source_key`가 snapshot 기준으로 확정되지 않습니다. 오래되거나 `None`인 font 값이 그대로 사용될 수 있습니다. 복수 snapshot 순서도 보장되지 않습니다. | `if "source_key" not in fonts_by_id[font_id]:`이므로 키가 존재하지만 값이 잘못된 경우 덮어쓰지 않습니다. 첫 snapshot만 선택하며 충돌 검사도 없습니다. | snapshot의 `(provider, provider_record_id)` 조합을 모아 하나인지 검증한 뒤 항상 그 값으로 설정하십시오. 서로 다른 조합이 나오면 `RuntimeError`로 중단하십시오. |
| `test_task3_integration.py:151-221` | “헬퍼 통합 테스트”가 실제 헬퍼를 호출하지 않습니다. 따라서 run 필터와 source key 파생을 증명하지 못합니다. | 테스트가 직접 `font_1["evidence_snapshots"] = [snapshot_1]`을 수행하고 `build_manifest(...)`만 호출합니다. `_make_font()`도 처음부터 `source_key`를 넣습니다. | 실제 `SupabaseAuditStore.get_current_fonts_with_snapshots()` 결과를 `build_manifest()`에 연결하십시오. source key 없음/`None`/충돌, 무관 폰트 제외까지 검증해야 합니다. |
| `audit_store.py:496-558` | 승인 UPDATE가 상태만 조건으로 걸어 검증 전체가 원자적이지 않습니다. 또한 metadata 전용이라는 설명과 달리 임의 stage를 허용하고 빈 검수자도 허용합니다. | 검증은 `current_stage != stage`뿐이며, UPDATE 조건은 `.eq("id", ...).eq("status", "needs_review")`뿐입니다. | `stage == "metadata"`와 비어 있지 않은 `reviewed_by`를 먼저 강제하십시오. UPDATE에도 `stage`, `field_name`, 필요하면 `auto_applicable=False` 조건을 함께 넣어 검증 시점과 갱신 시점 사이의 변경을 막으십시오. 현재 구현은 중복 승인만 안전합니다. |
| `test_main.py:260` | 기존 테스트가 아무것도 검증하지 않는 테스트로 약화됐습니다. | `mock_write.assert_called_once()`와 `assert result == 3`이 삭제됐습니다. | 두 assertion을 복원하십시오. 새 테스트는 별도 구역 또는 별도 파일로 이동하십시오. |
| `test_audit_store.py:80-230` | 조건부 승인 테스트가 실제 UPDATE 조건을 확인하지 않습니다. | 정상 테스트는 “예외가 발생하지 않음”만 확인합니다. `.eq("status", "needs_review")`가 삭제돼도 통과할 수 있습니다. | UPDATE payload, `reviewed_by`, `reviewed_at`, ID·status·stage·field 조건 호출을 명시적으로 검증하십시오. |

### Medium

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `__main__.py:697-704` | 일반 예외에서 예외 클래스만 기록해 장애 원인을 찾기 어렵습니다. | `logger.error("manifest 생성 실패: %s", exc.__class__.__name__)` | 시크릿을 제외한 안전한 메시지와 stack trace를 남기십시오. 설정·DB·스키마 오류를 가능하면 별도 예외로 나누는 편이 좋습니다. |
| `audit_store.py:764-871` | 반환값이 list인지 여부만 확인하고 각 행이 객체인지 검증하지 않습니다. | 이후 바로 `snapshot.get(...)`, `font.get(...)`을 호출합니다. | 각 행이 `Mapping`인지, ID와 provider 값이 비어 있지 않은지 검증하고 명확한 오류로 중단하십시오. |
| `audit_store.py:776-827` | 모든 컬럼을 조회해 성능과 데이터 노출 범위가 불필요하게 커집니다. | 세 쿼리가 모두 `.select("*")`이며 snapshot의 `raw_text`도 가져옵니다. | `build_manifest`에 필요한 컬럼만 명시하십시오. 페이지네이션 수정과 함께 처리하면 됩니다. |
| `test_audit_store.py:109-230` | `try/except ValueError` 테스트가 잘못된 이유로 발생한 ValueError도 성공 처리합니다. | 모든 예외 테스트가 메시지와 발생 지점을 확인하지 않습니다. | `pytest.raises(ValueError, match=...)`를 사용하십시오. |

### 긍정적 관찰

- metadata에서 `needs_review` 대신 `broken_count`를 검사하는 로직은 요구사항과 일치합니다.
- 10%는 통과하고 10% 초과만 차단해 기존 경계 조건을 유지했습니다.
- 크롤·파싱 예외를 `broken_count`로 분리한 방향이 적절합니다.
- legal/script의 기존 `needs_review` 게이트가 유지됩니다.
- build가 승인 작업을 수행하지 않아 승인과 산출 책임이 분리됐습니다.
- 승인 UPDATE에 `status="needs_review"` 조건을 둬 두 검수자의 중복 승인은 방지합니다.
- 이 diff에는 fonts DB나 prod를 직접 변경하는 코드가 없습니다.