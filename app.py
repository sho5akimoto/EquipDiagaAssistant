"""設備一次診断アシスタント Streamlit クライアント.

設備トラブル一次診断 API（/diagnose-equipment）を呼び出し、
診断結果を見やすいタブ形式で表示する Streamlit アプリケーション。
ファイルアップロードに加え、カメラ撮影による画像入力にも対応。

レスポンススキーマ:
    - priority: 優先度（level, reason）
    - assumed_causes: 想定原因リスト
      （文字列配列、最大3件）
    - diagnostic_steps: 診断手順リスト（action,
      expected_result, next_if_abnormal）
    - recommended_parts: 推奨交換部品リスト
      （文字列配列、最大5件）
    - estimated_time_hours: 推定作業時間
      （時間単位）
    - escalation_point: エスカレーション先
      （role, reason）
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import threading
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from streamlit_back_camera_input import back_camera_input

# -----------------------------------------------------------
# 環境変数から設定値を読み込む
# -----------------------------------------------------------
API_BASE_URL: str = os.environ.get(
    "API_BASE_URL", ""
).strip()
API_KEY: str = os.environ.get(
    "API_KEY", ""
).strip()


def parse_timeout(default: int = 120) -> int:
    """環境変数 API_TIMEOUT_SEC を秒として読み取る。

    未設定または不正な値の場合は *default* を返す。
    """
    raw = os.environ.get(
        "API_TIMEOUT_SEC", ""
    ).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


TIMEOUT_SEC: int = parse_timeout(120)

# ページ全体の設定（タイトル・レイアウト）
st.set_page_config(
    page_title="設備一次診断アシスタント",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# -----------------------------------------------------------
# グローバル CSS 注入（モダンテーマ）
# -----------------------------------------------------------
_CSS = """\
<style>
html, body, [class*="css"] {
  font-family: 'Yu Gothic','YuGothic',
    'Hiragino Kaku Gothic ProN','Meiryo',
    sans-serif;
  color: #1a1a1a;
}
.main .block-container { padding-top: 1.5rem; }

.hero-banner {
  background: #000;
  border-radius: 12px;
  padding: 28px 36px;
  margin-bottom: 24px;
  color: #fff;
  position: relative;
  overflow: hidden;
}
.hero-banner::before {
  content: '';
  position: absolute;
  top: -30%; right: -10%;
  width: 50%; height: 160%;
  background: linear-gradient(
    135deg, #575B7C 0%, #4455E4 100%
  );
  clip-path: polygon(
    60% 0%, 100% 0%, 100% 100%, 20% 100%
  );
  opacity: .18;
}
.hero-banner h1 {
  margin:0 0 4px;font-size:1.6rem;
  font-weight:700;position:relative;
  letter-spacing:0.02em;
}
.hero-banner p {
  margin:0;font-size:.9rem;
  opacity:.75;position:relative;
}

.section-card {
  background:#fff;
  border:1px solid #E8E8EC;
  border-radius:10px;padding:24px;
  margin-bottom:16px;
  box-shadow:0 2px 8px rgba(0,0,0,.04);
  transition:box-shadow .25s ease;
}
.section-card:hover {
  box-shadow:0 4px 16px rgba(0,0,0,.07);
}
.section-title {
  font-size:1.05rem;font-weight:700;
  color:#000;margin:0 0 16px;
  display:flex;align-items:center;gap:8px;
  border-bottom:2px solid #4455E4;
  padding-bottom:10px;
}
.section-title .icon {
  display:inline-flex;align-items:center;
  justify-content:center;
  width:30px;height:30px;
  border-radius:8px;font-size:15px;
}
.icon-blue{background:#E8E8EC}
.icon-slate{background:#E8E8EC}

.stTabs [data-baseweb="tab-list"]{
  gap:0;background:#E8E8EC;
  border-radius:8px;padding:3px;
}
.stTabs [data-baseweb="tab"]{
  border-radius:6px;font-weight:600;
  font-size:.85rem;padding:8px 14px;
  color:#575B7C;
}
.stTabs [aria-selected="true"]{
  background:#fff !important;
  color:#4455E4 !important;
  box-shadow:0 1px 3px rgba(0,0,0,.08);
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"]{
  display:none;
}

.priority-badge {
  display:inline-flex;align-items:center;
  gap:10px;padding:14px 24px;
  border-radius:10px;font-weight:700;
  font-size:1.25rem;margin:8px 0 16px;
}
.priority-badge .dot {
  width:12px;height:12px;border-radius:50%;
  animation:badge-pulse 2s ease-in-out infinite;
}
@keyframes badge-pulse {
  0%,100%{transform:scale(1);opacity:1}
  50%{transform:scale(1.25);opacity:.65}
}
.badge-critical {
  background:#fef2f2;
  color:#991b1b;border:1px solid #fecaca;
}
.badge-critical .dot{background:#DB3939}
.badge-important {
  background:#fffbeb;
  color:#92400e;border:1px solid #fde68a;
}
.badge-important .dot{background:#f59e0b}
.badge-normal {
  background:#eef2ff;
  color:#3730a3;border:1px solid #c7d2fe;
}
.badge-normal .dot{background:#4455E4}

.cause-card {
  display:flex;align-items:flex-start;
  gap:14px;padding:16px 18px;
  background:#fff;border:1px solid #E8E8EC;
  border-radius:8px;margin-bottom:10px;
  transition:all .2s ease;
}
.cause-card:hover {
  border-color:#8A96EF;
  box-shadow:0 4px 16px rgba(68,85,228,.08);
  transform:translateY(-1px);
}
.cause-num {
  flex-shrink:0;width:28px;height:28px;
  border-radius:8px;
  background:#4455E4;
  color:#fff;display:flex;
  align-items:center;justify-content:center;
  font-weight:700;font-size:.82rem;
}
.cause-text {
  font-size:.93rem;color:#1a1a1a;
  line-height:1.65;padding-top:2px;
}

.step-wrapper {
  display:flex;align-items:stretch;
  margin-bottom:8px;gap:12px;
}
.step-card {
  flex:1;min-width:0;background:#fff;
  border:1px solid #E8E8EC;
  border-radius:10px;overflow:hidden;
  box-shadow:0 1px 4px rgba(0,0,0,.03);
  transition:all .2s ease;
}
.step-card:hover {
  border-color:#8A96EF;
  box-shadow:0 4px 16px rgba(68,85,228,.08);
}
.step-header {
  background:#000;
  color:#fff;padding:10px 16px;
  font-weight:700;font-size:.85rem;
  letter-spacing:.04em;
}
.step-body td {
  padding:10px 16px;font-size:.88rem;
  border-bottom:1px solid #E8E8EC;
}
.step-body .label-cell {
  width:28%;font-weight:600;
  color:#575B7C;background:#f9f9fb;
}

.abnormal-arrow {
  display:flex;align-items:center;
  flex-shrink:0;
  color:#DB3939;font-size:2rem;
  font-weight:700;line-height:1;
  padding:0 2px;
  animation:arrow-pulse 1.5s ease-in-out infinite;
}
@keyframes arrow-pulse {
  0%,100%{opacity:1;transform:translateX(0)}
  50%{opacity:.6;transform:translateX(4px)}
}
.abnormal-box {
  display:flex;flex-direction:column;
  justify-content:center;
  flex-shrink:0;max-width:38%;
  background:#fef2f2;
  border:1px solid #fecaca;
  border-radius:8px;padding:12px 16px;
}
.abnormal-box .abnormal-title {
  font-size:.75rem;font-weight:700;
  color:#DB3939;
  margin-bottom:4px;
  letter-spacing:.03em;
}
.abnormal-box .text {
  font-size:.83rem;color:#991b1b;
  font-weight:600;line-height:1.5;
}

.flow-arrow {
  display:flex;justify-content:center;
  margin:4px 0 12px;
}
.flow-arrow-inner {
  display:flex;flex-direction:column;
  align-items:center;color:#8186A5;
}
.flow-arrow-inner .arrow-down {
  font-size:2rem;line-height:1;
  animation:arrow-bounce 2s ease infinite;
}
@keyframes arrow-bounce {
  0%,100%{transform:translateY(0)}
  50%{transform:translateY(4px)}
}

.parts-grid {
  display:flex;flex-wrap:wrap;
  gap:10px;margin-top:8px;
}
.part-chip {
  display:inline-flex;align-items:center;
  gap:8px;padding:10px 18px;
  background:#fff;border:1px solid #E8E8EC;
  border-radius:8px;font-size:.88rem;
  font-weight:500;color:#1a1a1a;
  transition:all .2s ease;
}
.part-chip:hover {
  border-color:#8A96EF;
  box-shadow:0 4px 12px rgba(68,85,228,.1);
  transform:translateY(-1px);
}
.part-chip .chip-icon {
  width:26px;height:26px;border-radius:6px;
  background:#4455E4;
  display:flex;align-items:center;
  justify-content:center;
  color:#fff;font-size:.78rem;
}

.metric-card {
  background:#eef2ff;
  border:1px solid #c7d2fe;
  border-radius:10px;padding:28px 24px;
  text-align:center;max-width:260px;
}
.metric-card .metric-value {
  font-size:2.6rem;font-weight:700;
  color:#4455E4;line-height:1;
  margin-bottom:6px;
}
.metric-card .metric-unit {
  font-size:1rem;color:#8A96EF;font-weight:600;
}
.metric-card .metric-label {
  font-size:.8rem;color:#727274;margin-top:8px;
}

.esc-card {
  background:#f9f9fb;
  border:1px solid #E8E8EC;
  border-left:4px solid #4455E4;
  border-radius:8px;padding:20px 24px;
  margin-bottom:12px;
}
.esc-card .esc-label {
  font-size:.75rem;font-weight:700;
  color:#575B7C;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:6px;
}
.esc-card .esc-value {
  font-size:1rem
  color:#000;line-height:1.5;
}

.summary-card {
  background:#f9f9fb;
  border:1px solid #E8E8EC;
  border-left:4px solid #4455E4;
  border-radius:8px;padding:20px 24px;
  margin-bottom:16px;
}
.summary-card ul {
  margin:0;padding-left:18px;
  color:#1a1a1a;line-height:1.8;
}
.summary-card li{font-size:.9rem}

.stButton > button[kind="primary"] {
  background:#4455E4 !important;
  border:none !important;
  border-radius:8px !important;
  font-weight:700 !important;
  font-size:1rem !important;
  padding:12px 24px !important;
  transition:all .25s ease !important;
  box-shadow:
    0 2px 8px rgba(68,85,228,.25) !important;
}
.stButton > button[kind="primary"]:hover {
  background:#3344cc !important;
  transform:translateY(-1px) !important;
  box-shadow:
    0 4px 14px rgba(68,85,228,.35) !important;
}

.empty-state {
  text-align:center;padding:48px 24px;
  color:#8186A5;
}
.empty-state .empty-icon {
  font-size:3rem;margin-bottom:12px;opacity:.4;
}
.empty-state .empty-text {
  font-size:.93rem;line-height:1.7;
}
</style>

"""

st.markdown(_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------
# API ウォームアップ（初回のみバックグラウンド実行）
# -----------------------------------------------------------
def wake_up_api() -> None:
    """API へ軽量リクエストを送りコールドスタート回避。"""
    if not API_BASE_URL or not API_KEY:
        return
    headers = {
        "x-api-key": API_KEY,
        "accept": "application/json",
    }
    data = {"query": "ping", "equipment": "ping"}
    try:
        requests.post(
            API_BASE_URL,
            headers=headers,
            data=data,
            timeout=5,
        )
    except Exception:
        return


if "warmed_up" not in st.session_state:
    thread = threading.Thread(
        target=wake_up_api, daemon=True
    )
    thread.start()
    st.session_state["warmed_up"] = True
    st.toast("AIエンジンを起動中...", icon="🚀")

# -----------------------------------------------------------
# 定数定義
# -----------------------------------------------------------
EQUIPMENT_OPTIONS: List[str] = [
    "PressA",
    "ConveyorX",
    "OvenZ",
    "CutterQ",
    "MixerM",
    "共通",
]


# -----------------------------------------------------------
# ユーティリティ関数
# -----------------------------------------------------------
def safe_dict(value: Any) -> Dict[str, Any]:
    """値が dict でなければ空辞書を返す安全変換。"""
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[Any]:
    """値が list でなければ空リストを返す安全変換。"""
    return value if isinstance(value, list) else []


def log_stdout(
    obj: Any, prefix: str = ""
) -> None:
    """デバッグ用にオブジェクトを標準出力へ整形出力。"""
    try:
        if isinstance(obj, (dict, list)):
            text = json.dumps(
                obj, ensure_ascii=False, indent=2
            )
        else:
            text = str(obj)
    except Exception:
        text = str(obj)
    if prefix:
        print(prefix)
    print(text, flush=True)


# -----------------------------------------------------------
# サマリー生成
# -----------------------------------------------------------
def build_summary_lines(
    result: Dict[str, Any],
) -> List[str]:
    """診断結果からサマリー文のリストを組み立てる。"""
    lines: List[str] = []

    pri = safe_dict(result.get("priority"))
    level = pri.get("level", "")
    if level:
        lines.append(f"優先度: <b>{level}</b>")

    causes = safe_list(
        result.get("assumed_causes")
    )
    if causes:
        top = "、".join(
            str(x) for x in causes[:2]
        )
        lines.append(f"想定原因: <b>{top}</b>")

    hours = result.get("estimated_time_hours")
    if hours is not None:
        lines.append(
            f"推定作業時間: <b>{hours} 時間</b>"
        )

    if not lines:
        lines.append(
            "診断結果を受信しました。"
            "下のタブから詳細を確認してください。"
        )
    return lines


# -----------------------------------------------------------
# UI 部品: 優先度バッジ
# -----------------------------------------------------------
def priority_badge_html(level: str) -> str:
    """優先度レベルに応じた色付きバッジ HTML を返す。"""
    if level in ("緊急", "高", "推奨"):
        cls = "badge-critical"
    elif level in ("重要", "中", "要検討"):
        cls = "badge-important"
    else:
        cls = "badge-normal"
    return (
        f'<div class="priority-badge {cls}">'
        f'<span class="dot"></span>'
        f"{level}</div>"
    )


# -----------------------------------------------------------
# UI 部品: 診断ステップカード
# -----------------------------------------------------------
def render_step_card(
    step_row: Dict[str, Any], step_no: int
) -> None:
    """診断手順1件をカード＋右矢印で描画する。

    カード内には「実施内容」「期待結果」を表示し、
    カード右側に矢印付きで「異常時の次対応」を表示。

    Args:
        step_row: 診断手順オブジェクト。
        step_no: 表示用のステップ番号（1始まり）。
    """
    action = step_row.get(
        "action", "（記載なし）"
    )
    expected = step_row.get(
        "expected_result", "（記載なし）"
    )
    abnormal = step_row.get(
        "next_if_abnormal", ""
    )

    card_html = (
        '<div class="step-card">'
        '<div class="step-header">'
        f"STEP {step_no}</div>"
        '<table class="step-body"'
        ' style="width:100%;'
        'border-collapse:collapse;">'
        '<tr><td class="label-cell">'
        "実施内容</td>"
        f"<td>{action}</td></tr>"
        '<tr><td class="label-cell">'
        "期待結果</td>"
        f"<td>{expected}</td></tr>"
        "</table></div>"
    )

    if abnormal:
        right_html = (
            '<div class="abnormal-arrow">' "\u2192" "</div>"
            '<div class="abnormal-box">'
            '<div class="abnormal-title">'
            "\u26a0 \u7570\u5e38\u3060\u3063\u305f\u5834\u5408</div>"
            '<div class="text">'
            f"{abnormal}</div></div>"
        )
    else:
        right_html = ""

    st.markdown(
        f'<div class="step-wrapper">'
        f"{card_html}{right_html}</div>",
        unsafe_allow_html=True,
    )


def render_flow_arrow() -> None:
    """診断ステップ間に下向き矢印を描画する。"""
    st.markdown(
        '<div class="flow-arrow">'
        '<div class="flow-arrow-inner">'
        '<div class="arrow-down">\u2193</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_diagnostic_flow(
    steps: List[Any],
) -> None:
    """診断手順リストをフロー形式で描画する。"""
    if not steps:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">\U0001f50d</div>'
            '<div class="empty-text">'
            "該当する診断手順はありません"
            "</div></div>",
            unsafe_allow_html=True,
        )
        return
    for idx, step in enumerate(steps):
        row = safe_dict(step)
        render_step_card(row, step_no=idx + 1)
        if idx < len(steps) - 1:
            render_flow_arrow()


# -----------------------------------------------------------
# API レスポンス正規化
# -----------------------------------------------------------
def normalize_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """API レスポンスを統一的な辞書形式に正規化。"""
    if not isinstance(result, dict):
        return {}
    if (
        "priority" in result
        and "assumed_causes" in result
    ):
        return result
    resp_obj = result.get("response")
    if isinstance(resp_obj, dict):
        return resp_obj
    return result


# -----------------------------------------------------------
# API 呼び出し
# -----------------------------------------------------------
def call_api(
    equipment: str,
    query_text: str,
    uploaded_file: Any,
) -> Dict[str, Any]:
    """診断 API を multipart/form-data で呼び出す。

    Args:
        equipment: 対象設備名。
        query_text: 症状や発生状況の自由記述。
        uploaded_file: UploadedFile 相当。

    Returns:
        正規化済みの診断結果辞書。

    Raises:
        requests.HTTPError: HTTP エラーの場合。
        requests.Timeout: タイムアウト発生時。
    """
    endpoint = (
        f"{API_BASE_URL.rstrip('/')}"
        "/diagnose-equipment"
    )

    mime = (
        getattr(uploaded_file, "type", None)
        or mimetypes.guess_type(
            uploaded_file.name
        )[0]
        or "application/octet-stream"
    )

    # ストリームを先頭に戻してから全バイトを読み取り、
    # 新しい BytesIO でラップして送信する。
    # Streamlit の UploadedFile は再実行時にストリームが
    # 消費済みになる場合があるため、常に新規バッファを使う。
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    file_bytes = uploaded_file.read()
    fresh = io.BytesIO(file_bytes)

    files = {
        "file": (
            uploaded_file.name,
            fresh,
            mime,
        )
    }
    data = {
        "equipment": equipment,
        "query": query_text,
    }
    headers = {
        "x-api-key": API_KEY,
        "accept": "application/json",
    }

    log_stdout(
        {
            "endpoint": endpoint,
            "timeout_sec": TIMEOUT_SEC,
            "equipment": equipment,
            "file_name": uploaded_file.name,
            "file_mime": mime,
            "query_len": len(query_text),
        },
        prefix="--- REQUEST DEBUG ---",
    )

    resp = requests.post(
        endpoint,
        headers=headers,
        data=data,
        files=files,
        timeout=TIMEOUT_SEC,
    )

    log_stdout(
        {
            "http_status": resp.status_code,
            "content_type": resp.headers.get(
                "content-type", ""
            ),
        },
        prefix="--- RESPONSE DEBUG ---",
    )

    if not resp.ok:
        log_stdout(
            resp.text,
            prefix="--- ERROR BODY (stdout) ---",
        )
        raise requests.HTTPError(
            f"HTTP {resp.status_code}",
            response=resp,
        )

    try:
        result: Dict[str, Any] = resp.json()
    except Exception:
        log_stdout(
            resp.text,
            prefix="--- NON-JSON BODY ---",
        )
        raise

    log_stdout(
        result,
        prefix="--- RESULT JSON (stdout) ---",
    )
    return normalize_result(result)


# ===========================================================
# メイン UI
# ===========================================================

# --- ヘッダーバナー ---
st.markdown(
    '<div class="hero-banner">'
    "<h1>\U0001f6e0\ufe0f 設備一次診断アシスタント</h1>"
    "<p>設備情報・症状・関連ファイルまたはカメラ写真を"
    "送信し、Leapnet による一次診断結果を表示します。</p>"
    "</div>",
    unsafe_allow_html=True,
)

# 必須環境変数チェック
if not API_BASE_URL or not API_KEY:
    st.error(
        "環境変数が不足しています。\n\n"
        "- API_BASE_URL"
        "（例: https://api.example.com）\n"
        "- API_KEY（x-api-key の値）\n"
        "- API_TIMEOUT_SEC"
        "（任意。未指定時は 120 秒）"
    )
    st.stop()

# セッション状態の初期化
for _key, _default in [
    ("last_result", None),
    ("summary_expanded", False),
    ("camera_mode", "idle"),
    ("captured_photo", None),
    ("input_source", None),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# 2カラムレイアウト
left, right = st.columns([1, 1], gap="large")

# -----------------------------------------------------------
# 左カラム: 診断条件入力フォーム
# -----------------------------------------------------------
with left:
    st.markdown(
        '<div class="section-card">'
        '<div class="section-title">'
        '<span class="icon icon-blue">'
        "\U0001f4dd</span>診断条件</div>",
        unsafe_allow_html=True,
    )

    selected_equipment = st.selectbox(
        "設備（必須）",
        options=[
            "選択してください",
        ] + EQUIPMENT_OPTIONS,
    )

    query_text = st.text_area(
        "現在の症状（必須）",
        height=120,
        placeholder=(
            "例：圧力が安定せず徐々に下がって"
            "います。オイル不足の可能性があります。"
        ),
    )

    # --- ファイルアップロード ---
    def _on_file_change() -> None:
        """ファイル選択時に入力ソースを記録。"""
        key = "file_uploader"
        if st.session_state.get(key) is not None:
            st.session_state[
                "input_source"
            ] = "file"

    file_from_uploader = st.file_uploader(
        "関連ファイル",
        type=None,
        help=(
            "画像、ログ、音声、動画、テキストなど。"
            "API仕様では file は必須です。"
        ),
        key="file_uploader",
        on_change=_on_file_change,
    )

    # --- カメラ撮影 ---
    cam = st.session_state["camera_mode"]
    if cam == "idle":
        if st.button(
            "\U0001f4f7 写真を撮る",
            use_container_width=True,
        ):
            st.session_state[
                "camera_mode"
            ] = "camera"
            st.rerun()
    elif cam == "camera":
        # 背面カメラをデフォルトで起動
        photo = back_camera_input(
            key="rear_cam",
        )
        if photo is not None:
            st.session_state[
                "captured_photo"
            ] = photo.getvalue()
            st.session_state[
                "camera_mode"
            ] = "preview"
            st.session_state[
                "input_source"
            ] = "camera"
            st.rerun()
    elif cam == "preview":
        st.image(
            st.session_state["captured_photo"],
            use_container_width=True,
        )
        if st.button(
            "\U0001f4f7 撮り直す",
            use_container_width=True,
        ):
            st.session_state[
                "camera_mode"
            ] = "camera"
            st.session_state[
                "captured_photo"
            ] = None
            st.rerun()

    # --- 後から操作した入力ソースを優先 ---
    has_file = file_from_uploader is not None
    has_photo = (
        st.session_state["captured_photo"]
        is not None
    )

    if has_file and has_photo:
        src = st.session_state["input_source"]
        if src == "camera":
            uploaded_file = io.BytesIO(
                st.session_state["captured_photo"]
            )
            uploaded_file.name = "camera_photo.jpg"
            uploaded_file.type = "image/jpeg"
            st.caption(
                "\u2192 カメラ写真が使用されます"
                "（後から操作）"
            )
        else:
            uploaded_file = file_from_uploader
            st.caption(
                "\u2192 アップロードファイルが"
                "使用されます（後から操作）"
            )
    elif has_photo:
        uploaded_file = io.BytesIO(
            st.session_state["captured_photo"]
        )
        uploaded_file.name = "camera_photo.jpg"
        uploaded_file.type = "image/jpeg"
    elif has_file:
        uploaded_file = file_from_uploader
    else:
        uploaded_file = None

    run = st.button(
        "\U0001f680 一次診断を実行",
        type="primary",
        use_container_width=True,
    )

    # セクションカード閉じタグ
    st.markdown("</div>", unsafe_allow_html=True)

    if run:
        errors: List[str] = []
        if selected_equipment == "選択してください":
            errors.append(
                "設備を選択してください。"
            )
        if not query_text.strip():
            errors.append(
                "現在の症状が未入力です。"
            )
        if uploaded_file is None:
            errors.append(
                "関連ファイルまたは写真が必要です。"
                "ファイルをアップロードするか、"
                "写真を撮影してください。"
            )

        if errors:
            for msg in errors:
                st.error(msg)
        else:
            try:
                st.session_state[
                    "last_result"
                ] = None
                with st.spinner(
                    "AIエージェント呼び出し中..."
                ):
                    st.session_state[
                        "last_result"
                    ] = call_api(
                        equipment=(
                            selected_equipment
                        ),
                        query_text=(
                            query_text.strip()
                        ),
                        uploaded_file=(
                            uploaded_file
                        ),
                    )
                    st.session_state[
                        "summary_expanded"
                    ] = True
            except requests.Timeout:
                st.error(
                    "タイムアウトしました。"
                    "API_TIMEOUT_SEC を延ばすか、"
                    "サーバ側を確認してください。"
                )
            except requests.HTTPError:
                st.error(
                    "API で HTTP エラーが発生。"
                    "詳細は標準出力ログを確認。"
                )
            except Exception as ex:
                log_stdout(
                    str(ex),
                    prefix=(
                        "--- UNEXPECTED ERROR ---"
                    ),
                )
                st.error(
                    "予期せぬエラーが発生。"
                    "詳細は標準出力ログを確認。"
                )

# -----------------------------------------------------------
# 右カラム: 診断結果表示
# -----------------------------------------------------------
with right:
    result = st.session_state.get("last_result")

    if not result:
        st.markdown(
            '<div class="section-card">'
            '<div class="empty-state">'
            '<div class="empty-icon">\U0001f4cb</div>'
            '<div class="empty-text">'
            "左側で条件を入力して<br>"
            "「一次診断を実行」を押すと、<br>"
            "ここに結果が表示されます。"
            "</div></div></div>",
            unsafe_allow_html=True,
        )
    else:
        # --- サマリーカード ---
        lines = build_summary_lines(result)
        items = "".join(
            f"<li>{ln}</li>" for ln in lines
        )
        st.markdown(
            '<div class="summary-card">'
            f"<ul>{items}</ul></div>",
            unsafe_allow_html=True,
        )

        # 必須キーチェック
        required_keys = {
            "priority",
            "assumed_causes",
            "diagnostic_steps",
            "recommended_parts",
            "estimated_time_hours",
            "escalation_point",
        }
        if (
            not isinstance(result, dict)
            or not required_keys.issubset(
                result.keys()
            )
        ):
            st.error(
                "応答スキーマが想定と異なります"
                "（標準出力ログを参照）。"
            )
            st.stop()

        # タブ構成（6タブ）
        tabs = st.tabs([
            "\u26a1 優先度",
            "\U0001f50d 想定原因",
            "\U0001f527 診断手順",
            "\U0001f4e6 推奨交換部品",
            "\u23f1 作業見積",
            "\U0001f4de エスカレーション",
        ])

        # --- 優先度タブ ---
        with tabs[0]:
            pri = safe_dict(
                result.get("priority")
            )
            level = pri.get("level", "（不明）")
            reason = pri.get("reason", "")

            st.markdown(
                priority_badge_html(level),
                unsafe_allow_html=True,
            )
            if reason:
                st.markdown(
                    '<div class="section-card">'
                    '<div class="section-title">'
                    '<span class="icon icon-slate">'
                    "\U0001f4a1</span>判断理由</div>"
                    f"<p>{reason}</p></div>",
                    unsafe_allow_html=True,
                )

        # --- 想定原因タブ ---
        with tabs[1]:
            causes = safe_list(
                result.get("assumed_causes")
            )
            if not causes:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">'
                    "\U0001f50d</div>"
                    '<div class="empty-text">'
                    "該当する想定原因はありません"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                for i, c in enumerate(causes, 1):
                    st.markdown(
                        '<div class="cause-card">'
                        '<div class="cause-num">'
                        f"{i}</div>"
                        '<div class="cause-text">'
                        f"{c}</div></div>",
                        unsafe_allow_html=True,
                    )

        # --- 診断手順タブ ---
        with tabs[2]:
            render_diagnostic_flow(
                safe_list(
                    result.get(
                        "diagnostic_steps"
                    )
                )
            )

        # --- 推奨交換部品タブ ---
        with tabs[3]:
            parts = safe_list(
                result.get("recommended_parts")
            )
            if not parts:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">'
                    "\U0001f4e6</div>"
                    '<div class="empty-text">'
                    "推奨部品なし"
                    "</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                chips = ""
                for j, p in enumerate(parts, 1):
                    chips += (
                        '<div class="part-chip">'
                        '<div class="chip-icon">'
                        f"{j}</div>{p}</div>"
                    )
                st.markdown(
                    '<div class="parts-grid">'
                    f"{chips}</div>",
                    unsafe_allow_html=True,
                )

        # --- 作業見積タブ ---
        with tabs[4]:
            hours = result.get(
                "estimated_time_hours"
            )
            if hours is not None:
                st.markdown(
                    '<div class="metric-card">'
                    '<div class="metric-value">'
                    f"{hours}</div>"
                    '<div class="metric-unit">'
                    "時間</div>"
                    '<div class="metric-label">'
                    "推定作業時間</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-icon">'
                    "\u23f1</div>"
                    '<div class="empty-text">'
                    "作業見積なし"
                    "</div></div>",
                    unsafe_allow_html=True,
                )

        # --- エスカレーションタブ ---
        with tabs[5]:
            esc = safe_dict(
                result.get("escalation_point")
            )
            role = esc.get("role", "")
            esc_reason = esc.get("reason", "")

            if role:
                st.markdown(
                    '<div class="esc-card">'
                    '<div class="esc-label">'
                    "役割</div>"
                    '<div class="esc-value">'
                    f"{role}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("（役割の提示なし）")

            if esc_reason:
                st.markdown(
                    '<div class="esc-card">'
                    '<div class="esc-label">'
                    "理由</div>"
                    '<div class="esc-value">'
                    f"{esc_reason}</div></div>",
                    unsafe_allow_html=True,
                )
