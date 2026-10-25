# クラウド開発環境

Python 3.12以上、Node.js 22以上。アプリ本体は静的HTMLで、ビルド・DB・ログイン・APIキーは不要です。Python仮想環境とブラウザはチェックアウト外に置きます。

```bash
cd /workspace/lifeplan-free
bash scripts/setup-cloud.sh
source /workspace/.lifeplan-venv/bin/activate
export CHROMIUM_PATH=/usr/bin/chromium  # system Chromiumがある今回の環境
export PLAYWRIGHT_BROWSERS_PATH=/workspace/.lifeplan-browsers
python automation/orchestration.py verify --root . --out reports/RUN_EVIDENCE.json
bash scripts/start-dev.sh
```

system ChromiumがなければsetupはPlaywright管理のChromiumを取得します。その場合CHROMIUM_PATHは指定せず、PLAYWRIGHT_BROWSERS_PATHだけ指定します。Linuxの共有ライブラリ不足は信頼できるOSパッケージ経由で導入し、TLS検証を無効にしないこと。

`start-dev.sh`は公開対象3ファイルだけを一時ディレクトリへコピーして内部HTTPサーバーを起動します。変更後は停止・再起動します。`.git/`、レビュー、家計情報、APIキーを配信しません。起動後は内部HTTPリクエストでindex.html、education-reserve.html、costs/official_sources.jsonの200と内容を確認します。UIにlocalhostプレビューURLは表示しません。

クラウドタスクは既に隔離されています。既存チェックアウトを使用し、利用者から明示的な指示がない限り新規Git worktreeを作らないこと。保存済みファイルや仮想環境は再利用できますが、サーバープロセスは新タスクで再起動が必要です。

ローカルCodexの開発には新しいモデルAPIキーは必要ありません。GitHub Issue起動の既存Gemini経路には、GitHub Actions側の既存GEMINI_API_KEYと無料枠が必要です。クラウド環境の変数へキーをコピーしないこと。無料枠・モデルアクセス・書込権限を確認できなければ外部実行済みと扱いません。

新規タスクへの復元と公開は、この実行中の環境の検証とは別です。環境設定で構成案を保存して公開後、別タスクで起動・検証してください。
