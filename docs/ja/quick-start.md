# App Store Connect Release：初心者向け画像付きガイド

[English](../en/quick-start.md) | [简体中文](../zh-CN/quick-start.md) | [日本語](quick-start.md) | [リポジトリのトップへ](../../README.md)

このガイドは、App Store Connect APIキーを初めて使う方を対象としています。手順を順番に進め、最初は読み取り専用の確認だけを行ってください。レポートを理解するまではアップロードしないでください。

> `SCHEMATIC` と表示された画像は説明用の模式図であり、Appleの画面を完全に再現したスクリーンショットではありません。Appleが画面構成を変更する場合がありますが、フィールド名と手順はApple公式ドキュメントで確認しています。

## 利用するルートを選ぶ

| ルート | 結果 | APIキー | Appleのデータを変更するか |
| --- | --- | --- | --- |
| A | ローカルのXcodeプロジェクトを監査 | 不要 | 変更しない |
| B | App Store Connectを照会 | 必要 | 変更しない |
| C | Archive、検証、アップロード | 必要 | 確認後のアップロードのみ |

初めて使う場合はルートAを完了してからルートBに進んでください。

## ステップ0：必要なものを確認する

- XcodeをインストールしたMac。
- `.xcodeproj` または `.xcworkspace` を含むフォルダ。
- そのフォルダとターミナルにアクセスできるCodex。
- ルートBまたはC：App Store Connectで対象アプリにアクセスできること。
- チームAPIキーを作成する場合：Account HolderまたはAdmin権限。

ローカルの読み取り専用監査だけならAPIキーは不要です。

## ステップ1：Skillをインストールする

ターミナルを開いて実行します。

```sh
git clone https://github.com/Hubuguilai/app-store-connect-release.git app-store-connect-release-repo
mkdir -p "$HOME/.codex/skills/app-store-connect-release"
rsync -a app-store-connect-release-repo/app-store-connect-release/ \
  "$HOME/.codex/skills/app-store-connect-release/"
```

![Skillのインストール](../assets/tutorial/03-install-skill-flow.png)

インストールを確認します。

```sh
test -f "$HOME/.codex/skills/app-store-connect-release/SKILL.md" \
  && echo "Skill installed successfully"
```

期待される結果：

```text
Skill installed successfully
```

インストール後、新しいCodexタスクを開始してください。

## ステップ2：ローカルの読み取り専用監査を実行する

CodexでXcodeプロジェクトを含むフォルダを開き、次のプロンプトをコピーします。

```text
$app-store-connect-release を使って、このXcodeプロジェクトを監査してください。
読み取り専用の確認だけを行い、Archive、アップロード、ファイル変更はしないでください。
```

Codexは、プロジェクトまたはWorkspace、Scheme、Bundle ID、チーム、プラットフォーム、バージョン、ビルド番号、署名設定を報告します。

成功の目安：

- Skillが認識されている。
- 正しいXcodeコンテナとSchemeが見つかっている。
- Archiveやアップロードのコマンドが実行されていない。
- 不足している前提条件が明確に表示されている。

ローカル監査だけが目的なら、ここで終了できます。ルートAは完了です。

## ステップ3：APIキーページを開く

App Store Connectを照会する場合、次の順に開きます。

```text
App Store Connect → ユーザとアクセス → 統合
→ App Store Connect API → チームキー
```

![App Store Connect APIキーページ](../assets/tutorial/01-app-store-connect-api-key-page.png)

画像の番号：

1. **統合**を開きます。
2. **チームキー**を選択します。
3. **Issuer ID**をコピーします。
4. `+` をクリックしてキーを作成します。
5. 作成された**Key ID**が一覧に表示されます。

画面に **Request Access** が表示される場合、まずAccount HolderがAPIアクセスを申請する必要があります。Appleが申請を審査します。チームキーや追加ボタンが見つからない場合は、Account HolderまたはAdminに作成を依頼してください。

## ステップ4：チームAPIキーを生成する

`+` または **Generate API Key** をクリックします。

![APIキー生成の模式図](../assets/tutorial/07-generate-api-key-schematic.png)

1. `Codex Release` など、用途が分かる名前を入力します。
2. 目的の作業に必要な最小権限のロールを選択します。
3. **Generate** をクリックします。

重要事項：

- Appleによると、チームキーの作成にはAccount HolderまたはAdmin権限が必要です。
- チームキーはアカウント内のすべてのアプリに適用されます。
- キー名とアクセスレベルは生成後に編集できません。
- 後で別のロールが必要になった場合は、キーを取り消して新しく作成します。

権限エラーを避けるためだけに広い権限を選ばないでください。最小限のロールから始め、必要なApple操作が拒否された場合にだけ権限変更を検討します。

## ステップ5：`.p8` ファイルを一度だけダウンロードする

キーを生成したら、そのダウンロードリンクをクリックします。

![APIキーのダウンロード模式図](../assets/tutorial/08-download-api-key-schematic.png)

1. ファイル名が `AuthKey_<KEY_ID>.p8` の形式であることを確認します。
2. 秘密鍵をダウンロードできるのは一度だけです。
3. **Download** をクリックして安全に保存します。

Appleは再ダウンロード可能なコピーを保存しません。紛失または漏えいした場合は、直ちにキーを取り消して新しいキーを作成してください。

禁止事項：

- 秘密鍵の内容をCodexやGitHub Issueに貼り付ける。
- `.p8` ファイルをGitにコミットする。
- Xcodeプロジェクト内に保存する。
- メールやチャットで送信する。

## ステップ6：キーを保存して設定する

実行前に `YOUR_KEY_ID` を実際のKey IDに置き換えます。

```sh
mkdir -p "$HOME/.appstoreconnect/private_keys"
mv "$HOME/Downloads/AuthKey_YOUR_KEY_ID.p8" \
  "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
chmod 600 "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

現在のターミナルセッションに認証情報を設定します。

```sh
export ASC_API_KEY_ID="YOUR_KEY_ID"
export ASC_API_ISSUER_ID="YOUR_ISSUER_ID"
export ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

![APIキー設定フロー](../assets/tutorial/02-api-key-setup-flow.png)

秘密鍵の内容を環境変数に入れないでください。`ASC_API_KEY_PATH` にはファイルのパスだけを指定します。

次回以降も利用する場合は、3行の `export` を `~/.zshrc` に追加し、ターミナルとCodexを再起動します。

## ステップ7：安全に認証をテストする

読み取り専用の認証テストを実行します。

```sh
python3 "$HOME/.codex/skills/app-store-connect-release/scripts/asc_api_client.py" auth
```

期待される結果：

```json
{
  "authenticated": true,
  "apps_returned": 1
}
```

`apps_returned` の数は環境によって異なります。`0` の場合は、キーのアカウントとロールが対象アプリにアクセスできるか確認してください。

これでルートBの設定は完了です。

## ステップ8：完全な読み取り専用監査を実行する

Codexでプロジェクトを開き、次をコピーします。

```text
$app-store-connect-release を使って、リリース準備状況を完全に監査してください。
App Store Connectの照会は許可しますが、メタデータ、スクリーンショット、IAP、
ファイル、署名アセット、ビルドを変更しないでください。アップロードもしないでください。
```

![読み取り専用監査の結果](../assets/tutorial/05-read-only-audit-result.png)

レポートで確認する項目：

- 正しいプロジェクトとScheme。
- 正しいBundle ID。
- 対象のバージョンとビルド番号。
- API認証の成功。
- `UPLOAD: NOT RUN`。

プロジェクト、Scheme、Bundle ID、バージョン、ビルド番号のどれかが違う場合は、先に進まないでください。

## ステップ9：リリースの各段階を理解する

![リリースフロー](../assets/tutorial/04-release-workflow.png)

1. **AUDIT**：プロジェクトとApple側の状態を確認します。
2. **ARCHIVE**：ローカルに `.xcarchive` を作成します。
3. **VALIDATE**：書き出した `.ipa` または `.pkg` をAppleで検証します。
4. **UPLOAD**：確認後にだけビルドを送信します。
5. **PROCESSING**：Appleによる処理を待ちます。
6. **VALID**：処理済みで選択可能な状態です。App Reviewの承認ではありません。

段階ごとに別のプロンプトを使用します。

アップロードせずにArchiveを作成：

```text
$app-store-connect-release を使ってRelease Archiveを作成してください。
アップロードせず、必要性が説明され承認されるまでProvisioningを更新しないでください。
```

アップロードせずにAppleで検証：

```text
$app-store-connect-release を使って新しいArchiveを書き出し、Appleで検証してください。
アップロードはしないでください。
```

処理状態を一度だけ確認：

```text
$app-store-connect-release を使って現在のビルド処理状態を読み取り専用で確認してください。
```

## ステップ10：対象を確認してからアップロードする

監査とAppleの検証が成功した場合にだけ使用します。

```text
$app-store-connect-release を使って検証済みパッケージをアップロードしてください。
最終確認の前に、正確なパッケージパス、Bundle ID、バージョン、ビルド番号、
Apple検証結果、重複ビルド確認結果を表示してください。App Reviewには提出しないでください。
```

![アップロード確認](../assets/tutorial/06-upload-confirmation.png)

確定する前に、次を自分で確認します。

- パッケージのファイル名とパス。
- Bundle ID。
- Marketing Version。
- Build Number。
- Appleの検証が成功している。
- 重複ビルドが見つかっていない。

アップロードには `--confirm-upload` が必要です。ビルドのアップロードはApp Reviewへの提出ではありません。

## コピーして使えるプロンプト

ローカルの読み取り専用確認：

```text
$app-store-connect-release を使ってこのプロジェクトを読み取り専用で監査してください。
```

Apple側の状態を確認：

```text
$app-store-connect-release を使ってApp Store Connectのバージョン、ビルド、
スクリーンショット、メタデータ、IAPの状態を確認してください。変更は適用しないでください。
```

メタデータの差分をプレビュー：

```text
$app-store-connect-release を使ってローカライズ済みメタデータの差分を
プレビューしてください。適用はしないでください。
```

1つのロケールのスクリーンショットをプレビュー：

```text
$app-store-connect-release を使ってen-USのスクリーンショット差分を確認してください。
アップロード、削除、置換はしないでください。
```

不安な場合は次を追加します。

```text
最初に計画を表示し、読み取り専用の確認だけを実行してください。
```

## よくある問題

### `ASC_API_ISSUER_ID is required`

現在のターミナルで3つの `export` をもう一度実行します。`~/.zshrc` に追加した場合は、ターミナルとCodexを再起動してください。

### `App Store Connect key file was not found`

正確なパスを確認します。

```sh
ls -l "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

ファイル名のKey IDと `ASC_API_KEY_ID` は一致する必要があります。

### `+` またはGenerate API Keyボタンがない

チームキーにはAccount HolderまたはAdmin権限が必要です。Account HolderがApp Store Connect APIへのアクセスをまだ申請していない可能性もあります。

### `Could not uniquely discover an Xcode workspace/project`

リポジトリ内に複数のXcodeコンテナがあります。リリース対象のアプリをCodexに明示するか、Workspace/Projectのパスを指定してください。

### `A unique scheme was not discovered`

CodexにScheme一覧を表示させ、対象の共有Schemeを明示的に選択します。

### 重複ビルド保護で停止した

Build Numberを上げてください。同じバージョンとビルド番号がAppleに存在する理由を確認せずに保護を回避しないでください。

### Xcodeが署名アクセスを要求する

ログインキーチェーンを解除し、証明書とプロファイルを確認します。Provisioningの更新は明示的に承認されるまで無効です。

## ポータルで手動対応が必要な項目

アプリとアカウントによっては、契約、税務・銀行情報、価格、販売地域、プライバシー回答、輸出コンプライアンス、年齢レーティング、レビュー連絡先、ビルド選択、IAPの関連付け、最終的なApp Review提出が必要です。

Skillはこれらを残作業として報告しなければなりません。ビルドがアップロードされたという理由だけで完了と判断してはいけません。

## Apple公式資料

- [App Store Connect APIを使い始める](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api)
- [App Store Connect APIキーを作成する](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api)
- [ロールの権限](https://developer.apple.com/help/app-store-connect/reference/account-management/role-permissions/)

---

[リポジトリのトップへ戻る](../../README.md)
