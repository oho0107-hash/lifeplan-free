# 継続開発の実行契約

Codexに自然言語で指示すると、ルートAGENTS.mdが作業規則となる。既存のIssue受付は`ai-dev.yml`を利用し、別の並行botや有料APIを追加しない。APIやGitHubの契約・権限がない状態で常駐稼働を保証しない。

## 実サブエージェント

`.codex/config.toml`はA01–A09、B01–B09、C01–C05を登録する。各`.codex/agents/*.toml`に責任、知識、成果物、検証基準、依存先を保存した。`docs/agent-roles.json`が機械可読一覧。作成者A04/A09のみworkspace-write、監査者はread-only。報告は親に返し、親が証拠を保存する。

Codex CLI 0.163.0の公式JSON schema（<https://raw.githubusercontent.com/openai/codex/rust-v0.163.0/codex-rs/core/config.schema.json>）に照合した。役割は`[agents.a01_orchestrator]`等の`description`/`config_file`と、役割別`sandbox_mode`/`developer_instructions`を使用する。モデルは利用環境の既存設定を継承し、新規API契約を要求しない。プロジェクト設定の読込みは環境/信頼設定に依存する。クラウドの提供ツールではAGENTS.mdに従い親が役割定義を担当に渡す。23役割の登録は23プロセスを常駐起動した意味ではない。

A01はまずA02/A03を起動し、制度に関係するB担当を選ぶ。C01は元要求から反例を探す。A04による実装とA05によるテスト後、A06/A07/C02/C04が元コード・仕様を別々に検証する。制度変更ではC03が原資料を再確認し、C05が最後に判定する。同じファイルの並行編集を避け担当範囲を明示し、既定の同時実行上限6・深さ1を守る。

## 要件・制度・証拠

`requirements.json`は初期構築の受入契約。各変更は同じ16項目で要件を追加する。`rule-ledger.json`は専門分野別の未確認を含む制度/計算台帳であり、未検証の出典を調査済みとみなさない。実行単位の`ORCHESTRATION.json`/`RUN_EVIDENCE.json`とレビュー記録を紐付ける。候補のハッシュが変われば以前の証拠を再利用しない。

標準検証はリポジトリルートで`python automation/orchestration.py verify --root . --out reports/RUN_EVIDENCE.json`。ブラウザでは入力・計算・保存復元・家族人数を架空データで確認する。計算変更では別言語の再計算と制度前提の確認を追加する。計算結果の一致は制度が正しい証拠にはならない。

PRでは変更前後、対象要件、受入条件、実際の実行コマンドと件数、未実行と失敗、一次資料の確認状況、リスクと切戻しを記載する。Critical=重大制度誤用/大幅誤算/秘密漏えい、High=重要計算/支援適用/主要機能不具合、Medium=限定条件や操作問題、Low=軽微表示。Critical/Highと重大未検証は公開停止。計算・法令税制給付・金額・セキュリティ・権限変更は必ず利用者承認後に公開する。

## 修正・停止・復旧

失敗→原因分析→必要なら要件へ差戻し→修正→影響テスト→独立レビューを最大3巡/30分で行う。APIの既存上限に先に達したら止める。改善しない場合、失敗を隠さず原因/試行/残件/必要な外部対応をレポートする。GitHub Actionsはジョブのtimeoutを別途適用する。

公開後確認は公開ページを取得するだけでなく、テストしたSHAの画面と重要操作を確認する。障害時は新規公開を止め、前の既知の検証済みコミットへrevert PRを作り同じ品質ゲートを通す。保護ルールの迂回や履歴の強制書換えはしない。権限がない場合は作成可能な差分/手順まで保存し、未実行を明記する。

## 費用と資格の限界

静的Pages、Python標準ライブラリ、Node標準テスト、Playwrightはこの構成で追加の有料APIを必要としない。Codex利用は既存プラン/実行枠に従い、無制限無料とは扱わない。GitHub Actionsの無料枠/ストレージ条件はリポジトリ可視性と契約で変わる。既存Geminiの無料枠・対象モデル・提供地域はプロジェクト次第であり、無料であるとコードのコメントだけから断定しない。クラウド側で新しいGemini keyを要求せず、ローカル検証はAPIを使わない。Issueによる実モデル実行は既存の安全なSecretと対象モデルの利用可否を確認してから行う。新規契約、課金モデルfallback、利用上限増加は無断で導入しない。

料金/運用条件の確認先（この文書だけで現契約の確認済みとはしない）：<https://developers.openai.com/codex/pricing/>、<https://docs.github.com/en/billing/concepts/product-billing/github-actions>、<https://ai.google.dev/gemini-api/docs/pricing>。API提供者への送信はアプリ利用者の家計データを含めず、公開してよい合成要求/コードに限る。
