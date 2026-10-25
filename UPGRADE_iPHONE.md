# iPhoneだけで自動開発拡張 v0.5 を導入する

対象: <https://github.com/oho0107-hash/lifeplan-free>

## まず注意

- **開いている不完全な実費調査PR #14は、まだマージしない。** 今回は別のPRで導入する。
- `main` の必須品質チェック `pr-quality-gate` は**解除しない**。
- 公開アプリを開き、入力データを「設定をバックアップ」で保存してから始める。
- アップロード先は必ず新しいブランチ。現在の家計本体は公開状態を維持する。

## 一度だけのファイル置き換え

1. GitHubの **Branches → New branch** で `education-autopilot-v05` を `main` から作成。
2. 本配布物の **3つのiPhone用ZIP** をiPhone「ファイル」で解凍。それぞれの中身を、必ず次のフォルダへアップロードする。

| 配布ファイル | GitHub保存先 | 中身 |
|---|---|---|
| `01_root_iPhone.zip` | `https://github.com/oho0107-hash/lifeplan-free/upload/education-autopilot-v05` | `index.html` `education-reserve.html` `README.md` `UPGRADE_iPHONE.md` |
| `02_automation_iPhone.zip` | `https://github.com/oho0107-hash/lifeplan-free/upload/education-autopilot-v05/automation` | Python改良・単体テスト・ブラウザテスト・スモークテスト |
| `03_workflows_iPhone.zip` | `https://github.com/oho0107-hash/lifeplan-free/upload/education-autopilot-v05/.github/workflows` | `ai-dev.yml` `pr-quality-gate.yml` `cost-source-check.yml` `agent-pages.yml` |

**GitHubにZIP自体をアップロードしない**。解凍したファイルだけを対応する場所にアップロードする。

3. `https://github.com/oho0107-hash/lifeplan-free/compare/main...education-autopilot-v05?expand=1` からPRを作成する。
4. PRの差分と `pr-quality-gate` を確認。`Expected` のままならPRの更新を待つか、手動の workflow_dispatch で **education-autopilot-v05** を対象に実行。今後の自動化は別の仕組みで改善する。
5. 全テストが緑色であること、変更対象が想定どおりであることを確認してマージ。重要な計算変更が無断で行われていないか確認する。
6. GitHub Pagesの新しい画面: `https://oho0107-hash.github.io/lifeplan-free/education-reserve.html` が表示されることを確認。

## 初回だけの認証設定（任意だが本格的な自動化には推奨）

これまでの「Approve workflows to run」は、GitHub Actions内の `GITHUB_TOKEN` が作るPRで起こり得る。GitHub公式仕様では、専用GitHub Appのinstallation tokenまたは個人Fine-grained PATをPRの**作成時に限って**使うことで避けられる場合がある。

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens。対象を `oho0107-hash/lifeplan-free` だけに限定。
2. 有効期限を短めに設定。最小限の権限を選ぶ。PR作成・マージに必要な **Contents: Read and write、Pull requests: Read and write** に加え、Issueへのコメントを続ける場合は **Issues: Read and write**。Account-wide / 全リポジトリ権限は不要。権限を広げる場合は理由を確認。
3. トークンは表示されたら一度だけコピーし、GitHubリポジトリの `Settings → Secrets and variables → Actions → New repository secret` から **`LIFEPLAN_PR_TOKEN`** の名前で登録。**このチャット、Issue、ファイルに貼らない。**
4. リポジトリの Settings → General → Pull Requests で **Allow auto-merge** をON。`main` の必須品質チェックを保護し続ける。
5. 以降のAI作成PRは、認証が有効ならGitHub PRテストが自動開始しやすくなる。資料だけのPRやCSSのみのPRは、**必須テストを通った場合だけ**自動マージが予約される。計算ルール・コード・制度・データ定義の変更は常に承認待ち。

**有効期限切れ・権限不足の場合**: fallback の標準トークンでPR作成するので、以前のようにワークフロー承認が必要になることがあります。再登録はGitHub Secretだけで行い、他の設定ファイルの再アップロードは不要。

## 日々の運用

- 毎週、登録済みの学校・塾の公式ページを自動チェック。前回からの内容変更があれば「学費更新要確認」というGitHub Issueを自動生成。価格をAIが推測して本番計算に入れることはしない。
- **開発要望の受付**は従来の GitHub Issue で自動化。ChatGPTから直接Issue登録するには、書込操作に対応したGitHub接続が別途必要。接続されていなければ Issue投稿操作は残る。
- 個別学校の費用は「公式学校料金」「校内納付以外」「塾」「受験」「大学生活」「支援金」を分離。安心準備額の画面では、金額不足のチェックリストと現在実費／通常／厳しめ／予備金を並べる。
- 現時点で登録済みの公式ページは高校・大学も含むが、全費目の検証と将来進学先の特定は未完了。**日常運用は完全放置を目標にするが、事実確認ができない教育費を正確に保証することはできない。**

## 自動化の安全柵

- PR `reviews/...`、`costs/issue-*.json`、`costs/coverage-issue-*.json` の調査資料のみ、または安全なCSS変更だけ自動マージ候補。
- `.github/workflows`、`automation`、学校の金額定義、`engine.js`、計算式の変更は人の承認が必要。
- 人間が承認する場合も `pr-quality-gate` を必須とし、チェックを無効化しない。
- `index.html` 以外に配信されるのは `education-reserve.html` と `costs/official_sources.json` のみ。GitHub Pagesに秘密情報は配信しない。

## Codexから継続開発する場合

この構築以降、通常の依頼ではZIPの手動差し替えは不要です。Codexで対象リポジトリを開き、自然言語で要望を送信します。`AGENTS.md`の手順に従い要件・専門検証・反証・実装・テスト・PRまで進みます。制度や計算・金額・権限の変更は、証拠付きPRの承認後に公開します。未解決の重大な計算差異がある間は新規公開が停止します。

環境の構成案の公開と、アプリのGitHub Pages公開は別操作です。APIキーや家庭の実データはIssue・PR・チャットに貼らないでください。
