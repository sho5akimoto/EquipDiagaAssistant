# EquipDiag - 設備トラブル一次診断

AIを活用した設備トラブルの一次診断アシスタントです。

本プロジェクトは、StreamlitベースのUIから診断API（/diagnose-equipment）を呼び出し、
現場でのトラブルシューティングを支援します。

---

## 🚀 概要

EquipDiagは以下を実現します：

- 設備トラブルの**一次診断の高速化**
- テキスト＋ファイル（画像・ログ等）による分析
- 構造化された診断結果の提示

---

## 🧠 主な機能

### 1. マルチモーダル入力
- 症状テキスト入力
- ファイルアップロード（画像・ログ・動画など）
- カメラ撮影対応

### 2. 構造化された診断結果
以下の情報をタブ形式で表示：

- 優先度
- 想定原因
- 診断手順
- 推奨交換部品
- 作業見積
- エスカレーション先

### 3. 現場向けUI
- 左右2カラム構成（入力 / 結果）
- ステップ形式の診断フロー表示
- 優先度の視覚強調

---

## 🏗 アーキテクチャ

[ユーザー入力]
   ↓
[Streamlit UI]
   ↓
[診断API (/diagnose-equipment)]
   ↓
[JSONレスポンス]
   ↓
[結果表示]

---

## 📦 必要環境

- Python 3.10以上
- streamlit
- requests

インストール：

pip install streamlit requests

---

## ⚙️ 環境変数

以下を設定してください：

API_BASE_URL=https://your-api-endpoint
API_KEY=your-api-key
API_TIMEOUT_SEC=120（任意）

---

## ▶️ 実行方法

streamlit run app.py

ブラウザで以下にアクセス：
http://localhost:8501

---

## 📡 API仕様

エンドポイント：

POST /diagnose-equipment

リクエスト：
- multipart/form-data
  - file: ファイル（必須）
  - equipment: 設備名
  - query: 症状

レスポンス例：

{
  "priority": {
    "level": "重要",
    "reason": "安全リスクあり"
  },
  "assumed_causes": ["ヒーター劣化"],
  "diagnostic_steps": [
    {
      "action": "電源確認",
      "expected_result": "正常動作",
      "next_if_abnormal": "電源交換"
    }
  ],
  "recommended_parts": ["ヒーター"],
  "estimated_time_hours": 2,
  "escalation_point": {
    "role": "保守担当",
    "reason": "専門対応が必要"
  }
}

---

## 🖥 UI実装

メインアプリ：
app.py

特徴：
- 2カラム固定レイアウト
- タブ形式で結果表示
- デバッグログは標準出力へ

---

## 🧪 利用例

入力：
- 設備：OvenZ
- 症状：温度の立ち上がりが遅い
- 画像：ヒーター部分

出力：
- 優先度：重要
- 想定原因：ヒーター劣化
- 次の対応：抵抗値確認

---

## 🎯 想定ユーザー

- 製造現場オペレーター
- 保全担当者
- フィールドエンジニア

---

## ⚠️ 注意事項

- バックエンドAPIが必要です
- レスポンス形式が異なるとUIが正常に動作しません

---

## 📄 ライセンス

MIT（任意で変更可能）

---

## 👤 作成者

Shogo Akimoto

---

## 🔥 今後の拡張

- 過去履歴とのRAG連携
- IoTデータ連携
- チケット自動発行
- モバイル最適化
