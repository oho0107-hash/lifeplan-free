# 要件と検証の対応

`requirements.json`は初期構築の受入項目を列挙したカタログで、各受入ケースは`unrun`が初期値。これは現在の実行報告ではない。以下の実ファイル/コマンドと、作業ごとの`RUN_EVIDENCE.json`、CIのログ、独立監査を合わせて判定する。文書や役割の存在だけで自然言語から本番までの合格を宣言しない。

| 要件 | 検証実装/証拠 | 判定の範囲 |
|---|---|---|
| ORG-001 | `automation/test_agent_contract.py`、公式v0.163.0 schemaとのTOML照合 | 全23役割の登録・内容・監査read-only。新タスクでの自動ロードは別確認。 |
| ORG-002 | `automation/test_orchestration.py`、`ORCHESTRATION.json` | 要件と受入ID、候補hash、未実行/未検証を保存。実モデルの妥当性は別。 |
| QA-001 | `automation/test_independent_finance.py`、`reviews/initial-audit.md` | Python独立算法・JSソース/配布HTML双方・反例。strict診断に未解決Highが3件ある。 |
| DATA-001 | `automation/test_agent_contract.py`、`rule-ledger.json`、`costs/official_sources.json` | 出典/年度/未確認区分。現行制度全体の確認済みという意味ではない。 |
| CI-001 | `.github/workflows/pr-quality-gate.yml`、`agent-pages.yml` | 同じ検証後にのみ公開。GitHub実設定/権限/実行は未確認なら未検証。 |
| AUTO-001 | `ai-dev.yml` concurrency/既存PR再利用、runner呼出/時間上限、`test_orchestration.py` | ローカルの有限性検証とworkflow検査。本番同時実行は別検証。 |
| SEC-001 | `automation/test_guard.py`、workflowの権限/secret分離検査 | 外部patch許可範囲と候補実行への秘密注入なし。完全な侵入試験ではない。 |
| APP-001 | `automation/test_smoke.cjs`、`automation/test_browser.py` | 埋込エンジン一致・主要フォーム/保存/資金不足。実機Safari/VoiceOverは未実施。 |
| APP-002 | `reviews/initial-audit.md`、独立金融診断JSON | 家計/ローン/教育の不足と反例。未実装機能を実装済みとしない。 |
| OPS-001 | `docs/IPHONE_OPERATIONS.md`、`test_orchestration.py` | 自然言語要求のローカル実証と重要変更の公開禁止。本番Issue→PRは認証次第。 |
| REL-001 | `automation/test_release_policy.py`、公開workflow、独立strict診断 | 計算/制度/データ/権限変更の承認待ち。現在High未解決のため公開不可。 |
| ENV-001 | `docs/environment.md`、クラウド設定のinstall_script/start_skill | 現環境でのテスト/ブラウザ動作と再利用手順保存。新snapshot復元とは別。 |

## 優先修正が必要な反例

| 要件 | 不具合ID | 受入入力と期待 | 現状/対応 |
|---|---|---|---|
| APP-002/QA-001 | FIN-BONUS-001 | 借入120万円・1年・12%・半年利6%の2回返済で総額1,309,049円 | 1,277,738円、High。ボーナス月・支払時点の仕様確定後に修正。 |
| APP-002/QA-001 | FIN-LEAVE-001 | 月20万円・12月出生・休業なしなら年給与240万円 | 0円、High。休業入力の不足を含む。給付額の制度判定とは別。 |
| APP-002/QA-001 | FIN-INFLATION-001 | 生活費100万円・2%・既卒子・翌年なら102万円 | 100万円、High。長期物価計算の仕様確定後に修正。 |

修正後は該当反例の期待値と全回帰テストを実行し、独立担当による再計算・制度前提の検証・利用者承認を得る。既知の差異をテスト削除や警告化で隠さない。
