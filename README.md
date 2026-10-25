# LIFE / ライフプラン（iPhone + GitHub Pages）

GASなし・ログイン不要の家計シミュレーター。公開URL: <https://oho0107-hash.github.io/lifeplan-free/>

## 新しい機能（自動化拡張 v0.5）

- `education-reserve.html`: 中学・高校・大学・塾・予備校・大学生の生活費など14分類の**証拠付き教育費・安心準備額**の試算画面。`index.html`から開く。家計の既存キャッシュフロー計算式は変更していない。
- `automation/assurance_budget.py`: 学校・学部を混ぜず、月額／年額／入学時の区別、学費上昇率と予備資金、費目の網羅性を判定する純粋計算エンジン。合算の根拠がない費目は「未完成」。**金額の保証ではない**。
- `automation/cost_research.py`: 高校と大学を含む登録済みの学校の公式料金表を取得する。複数学部が載るHTMLでは学部の明示により取り違えを減らす。PDFを含む多様な形式の正確な抽出には、引き続き検証が必要。
- `cost-source-check.yml`: 登録済み公式ページを毎週再取得し、前回と比べた変化があれば**要確認のIssue**を自動作成。変更通知＝値上げの確定ではない。現在は16件の候補ページを監視。
- `ai-dev.yml`: 通常のIssueからAIによる要件・レビュー・修正・テスト・PR作成。任意の専用トークンを一度だけ設定すると、PRテストの手動承認を減らせる。
- `release_policy.py`: 調査レポートだけ、または厳格なCSS単独変更のみ自動マージ候補。計算・データ・セキュリティ・workflow変更は必ず人のマージ承認。

## 大切な限界

1. 大学・高校の**すべての公式料金が収集済みではない**。公式ページ16件を登録しただけで、費目網羅は別の検証が必要。希望学校や学部が未登録なら許可済み公式URLの登録が必要。
2. 教育費の金額を100%「確実に足りる」と保証することは不可能。将来の値上げ・進路・通学形態・予備校選択などについて、前提を置いた保守的な準備額を別表示する。
3. 未確認費用は0円としない。学校の公式資料に記載のない費用は本人確認済みの見積・価格情報、または根拠と算定前提を明示した予備額として計上。未確認項目が残る場合は「未完成」と表示。
4. アプリのメインキャッシュフローへ新しい準備額は**未接続**。計算ルールに関わる自動変更を避けた。既存の家計試算は旧教育費モデルを使う。次の実装では、承認済みの準備額だけを年別キャッシュフローへ反映する必要がある。
5. PR作成後の完全自動テスト・自動マージは、GitHubの設定と認証に依存する。本番環境では未検証。AIの無料枠制限では中断する。
6. GitHubリポジトリは公開なので、GitHub Issueやコードに家族の収入・住所・生年月日などの個人情報やAPIキーを記載しない。試算データは端末内保存で扱う。

## インストール

iPhone向け詳細: [`UPGRADE_iPHONE.md`](UPGRADE_iPHONE.md)。`main`ブランチの保護を維持したまま、修正用ブランチへファイルを配置し、PRを作成する。

`LIFEPLAN_PR_TOKEN` は任意のGitHub Secret（権限を必要最低限にした期限付きのFine-grained PAT）。**Gemini APIキーとは別**。登録しなくても動作するが、PRテストの実行承認は残り得る。AIが実行するgenerate/verifyジョブには渡さない。詳細はガイドを参照。

## ローカル・GitHub Actionsのテスト

```bash
python -m unittest discover -s automation -p test_assurance_budget.py -q
python -m unittest discover -s automation -p test_release_policy.py -q
python -m unittest discover -s automation -p test_source_change_report.py -q
node --test automation/test_smoke.cjs
```

ブラウザテストにはPlaywright Chromiumが必要（Actionsでインストール）。

## 継続開発体制（今回の構築）

自然言語の変更指示はCodexでこのリポジトリを開いて送ります。永続ルールは [AGENTS.md](AGENTS.md)、専門担当の設定は `.codex/agents/` にあります。環境の導入・起動は [クラウド環境手順](docs/environment.md)、証拠・未解決事項は `docs/` と `reviews/initial-audit.md` を参照してください。

新しい品質ゲートは、テスト成功と制度の正しさを分けて記録します。重大な計算差異が残る間は新しいPages公開を停止します。既存公開サイトが修正済みになった意味ではありません。GitHubでのPR・公開・実機Safari検証の完了は、実際の結果が得られた場合だけ報告します。
