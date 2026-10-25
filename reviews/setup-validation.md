# 初期構築の実行結果 — 2026-10-25（日本時間）

## 現環境で確認したこと

- Python 3.12.14 / Node.js 24.19.0 / system Chromium。`requirements-dev.txt`で依存と間接依存を固定し、`/workspace/.lifeplan-venv`へ導入。`scripts/setup-cloud.sh`の再実行成功。
- `CHROMIUM_PATH=/usr/bin/chromium /workspace/.lifeplan-venv/bin/python automation/orchestration.py verify --root . --out reports/RUN_EVIDENCE.json` 成功。検証中の対象ファイル変更なし。
- Python 94テスト成功、失敗/エラー/skip/expectedFailure/unexpectedSuccessすべて0。Node既存回帰5テスト成功。
- Chromium 390pxで入力・計算・4人目・端末保存・資金不足・教育費未完成表示。追加でJSONバックアップ/復元/再読込、不正/配列/過大JSON拒否、検証操作中の外部リクエストなしを確認。
- オフライン実証2種類：合成の自然言語要求とモデル応答fixtureからCSS候補と仮想計算候補を作り、exact patch guard、候補hash、実Node回帰、未検証draft/公開禁止まで実行。実モデル・GitHubサービスのE2Eではない。
- Codex 23役割設定をTOML構文と公式0.163.0 schemaへ照合。役割/要件/台帳の契約3テストも94件に含む。新タスクの自動ロードは未実証。
- CI担当が公式SHA256確認済みactionlintで全6 workflowを検証。元のparser回帰23テストを上書き候補とは別に保全して実行。
- 実サブエージェントによる実装・独立計算・セキュリティレビューを実施。指摘後にテストプロセス分離、元テスト保全、draft強制、永続役割のIssue経路への接続を修正。既存guardの呼出役割互換エラーも修正し、全体を再検証した。
- `scripts/start-dev.sh`を実起動。公開3ファイルの内部HTTP 200と本文、`.git/config`/automation/reviewsの404を確認。
- engine.js、配布HTML、教育費画面、公式料金登録データに変更なし。既存計算の正しさを保証した意味ではない。

## 成功した回帰テストとは別の公開判定

`python automation/test_independent_finance.py --diagnose --output reports/finance-diagnostics.json --strict` は終了コード1。High3件（FIN-BONUS-001、FIN-LEAVE-001、FIN-INFLATION-001）を再現し、`publication_allowed=false`。金額と反例は[初期監査](initial-audit.md)に記録。回帰greenで公開禁止を解除しない。

## 保存した環境構成

クラウド構成案の `install_script` / `start_skill` と、既存custom allowlistを維持した `api.github.com` / `results-receiver.actions.githubusercontent.com` 追加を保存済み。保存成功は実行/適用/公開とは別。環境設定で構成案を保存して公開し、新しいタスクで復元・起動を検証する必要がある。

## 未完了・外部制約

- Git HTTPSのread/push成功。`setup/autonomous-development` を送信し、草案PR #20を実作成した（https://github.com/oho0107-hash/lifeplan-free/pull/20）。初回GitHub APIはCONNECT 403だったが、接続先追加後の再試行でPR作成・参照に成功。既存認証を再利用し、新規tokenは要求していない。
- GitHub Actionsの実PR品質検証（run 40171010168）はsuccess、金融診断（run 40171010134）はfailure。前者は依存導入・検証・証拠uploadの成功をAPIで確認。後者のローカル同一診断ではHigh3件を再現したが、リモート詳細ログの取得はネットワーク拒否で未照合。
- mainのbranch protection、Actions secrets/variablesのメタデータ読取は403 Resource not accessible by integration。保護設定とGitHub側secretの有無は確認できず、変更していない。
- GEMINI_API_KEYは現クラウドに存在しない。GitHub Actions側secretの有無・無料枠・対象モデル・現契約料金は未確認。新規API課金は導入していない。Codex直接開発とオフライン検証はこのキー不要。
- Issue経路は一般的な新規受入テストの自動生成・独立実行・出典照合をまだ完結しない。候補は常に証拠待ちのdraftとし、無条件の自動公開体制完成とは扱わない。Codex直接タスクではAGENTS.mdに従い担当が必要な実テストを追加・実行する。
- 実機iPhone Safari/WebKit/VoiceOver、全制度の最新一次資料、公開後の実機操作、復旧実行、新タスクsnapshot復元は未検証。
- 生成Pythonの検証runnerはAPIキー/書込トークンを渡さない一時環境だが、敵対的コードに対する完全な隔離とは保証しない。PR回復はdraft作成のみ。元runのartifact実体と候補・証拠を照合し、期限切れ/取得不能時は停止する。ローカルfixture6ケースで検証し、GitHub実回復は未実施。

開発・検証環境は利用可能。アプリの計算精度と外部連携を含む開発体制の全受入完了・公開済みとは宣言しない。
