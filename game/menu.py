"""ゲーム起動時のセットアップ画面（BLEデバイス選択 → モード選択）。

レトロゲームっぽい質感を保つため、専用UIライブラリは使わずシンプルな
テキストリスト + マウスクリックで作る。

戻り値:
    (speed_source, cleanup) のタプル。`cleanup()` はゲーム終了時に呼ぶこと
    （Bleak スレッドの片付け）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import pygame

from game import config as C
from game import display as D
from game.ble import BleBridge, BridgeEvent, DeviceCandidate, DeviceProfile
from game.speed_source import (
    BleSpeedSource,
    ConstantSpeedSource,
    Mode,
    SpeedSource,
)

log = logging.getLogger(__name__)


# --- 画面状態 ---
_S_TITLE = "title"
_S_SCANNING = "scanning"
_S_DEVICE_SELECT = "device_select"
_S_CONNECTING = "connecting"
_S_MODE_SELECT = "mode_select"
_S_DONE = "done"


@dataclass
class _MenuItem:
    label: str
    enabled: bool = True
    payload: object = None
    sublabel: str = ""

    def render(self, font: pygame.font.Font) -> pygame.Surface:
        color = (240, 240, 240) if self.enabled else (110, 110, 110)
        return font.render(self.label, True, color)


def run_setup(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
) -> tuple[SpeedSource, Callable[[], None]]:
    # Windows で日本語が出るフォント順に指定（最初に見つかったものが使われる）
    jp_fonts = "yugothicui,yugothic,meiryo,msgothic,consolas"
    title_font = pygame.font.SysFont(jp_fonts, 56, bold=True)
    item_font = pygame.font.SysFont(jp_fonts, 32, bold=True)
    sub_font = pygame.font.SysFont(jp_fonts, 22)
    hint_font = pygame.font.SysFont(jp_fonts, 20)

    # BLE bridge は初期化に失敗することがある（OS側Bluetooth無効など）。
    # 失敗してもメニュー自体は出して、デモ走行を選べるようにする。
    bridge: BleBridge | None = None
    bridge_error: str | None = None
    try:
        bridge = BleBridge()
    except Exception as e:
        bridge_error = f"BLE初期化失敗: {e}"
        log.warning(bridge_error)

    state = _S_TITLE
    devices: dict[str, DeviceCandidate] = {}
    selected_device: DeviceCandidate | None = None
    connect_features: dict[str, bool] = {}
    error_msg: str | None = bridge_error
    info_msg: str | None = None

    # 結果（決定したら _S_DONE に遷移して return）
    result_source: SpeedSource | None = None

    def _items_for_state() -> list[_MenuItem]:
        if state == _S_TITLE:
            return [
                _MenuItem("BLEデバイスを検索", enabled=bridge is not None),
                _MenuItem("デモ走行（30km/h 固定）", payload="demo"),
            ]
        if state == _S_DEVICE_SELECT:
            items: list[_MenuItem] = []
            # 広告UUIDで CSC/CPS と分かるものを上に出す（推測タグ）
            ordered = sorted(
                devices.values(),
                key=lambda d: (not d.profiles, -(d.rssi or -999), d.name),
            )
            for d in ordered:
                if d.profiles:
                    prof = "/".join(p.value.upper() for p in d.profiles)
                    tag = f"[{prof}] "
                else:
                    tag = ""
                rssi = f"  {d.rssi} dBm" if d.rssi is not None else ""
                items.append(_MenuItem(
                    label=d.name,
                    sublabel=f"{tag}{d.address}{rssi}",
                    payload=d,
                ))
            items.append(_MenuItem("← 戻る (再スキャン可)", payload="back"))
            return items
        if state == _S_MODE_SELECT:
            assert selected_device is not None
            has_cps = DeviceProfile.CPS in selected_device.profiles
            has_csc = DeviceProfile.CSC in selected_device.profiles
            wheel = connect_features.get("wheel", True)
            crank = connect_features.get("crank", True)
            power = connect_features.get("power", has_cps)

            items: list[_MenuItem] = []
            items.append(_MenuItem(
                "SPEED  (ホイール回転 → 速度)",
                enabled=wheel,
                payload=Mode.SPEED,
                sublabel="センサー速度をそのまま使用",
            ))
            items.append(_MenuItem(
                "CADENCE  (クランク回転 → 速度推定)",
                enabled=crank,
                payload=Mode.CADENCE,
                sublabel="ケイデンス/3 を飽和速度に",
            ))
            items.append(_MenuItem(
                "POWER  (パワー → 速度推定)",
                enabled=power,
                payload=Mode.POWER,
                sublabel="log10(3 + power) × 15 を飽和速度に",
            ))
            items.append(_MenuItem("← 戻る", payload="back"))
            return items
        return []

    def _draw_header(text: str, sub: str | None = None) -> None:
        screen.fill((10, 14, 22))
        title_surf = title_font.render("路線Rider", True, (255, 200, 80))
        screen.blit(title_surf, (60, 60))
        head_surf = item_font.render(text, True, (200, 220, 255))
        screen.blit(head_surf, (60, 150))
        if sub:
            sub_surf = sub_font.render(sub, True, (160, 180, 200))
            screen.blit(sub_surf, (60, 200))

    def _draw_items(items: list[_MenuItem], mouse_pos: tuple[int, int]) -> list[pygame.Rect]:
        rects: list[pygame.Rect] = []
        y = 260
        for i, item in enumerate(items):
            label_surf = item.render(item_font)
            row_rect = pygame.Rect(60, y, C.SCREEN_W - 120, 60)
            hover = item.enabled and row_rect.collidepoint(mouse_pos)
            if hover:
                pygame.draw.rect(screen, (40, 70, 110), row_rect, border_radius=8)
            screen.blit(label_surf, (80, y + 8))
            if item.sublabel:
                sub_surf = sub_font.render(item.sublabel, True, (150, 170, 190))
                screen.blit(sub_surf, (80, y + 36))
            rects.append(row_rect)
            y += 72
        return rects

    def _draw_footer(hint: str) -> None:
        hint_surf = hint_font.render(hint, True, (150, 150, 150))
        screen.blit(hint_surf, (60, C.SCREEN_H - 50))
        if error_msg:
            err_surf = hint_font.render(error_msg, True, (255, 120, 120))
            screen.blit(err_surf, (60, C.SCREEN_H - 80))
        if info_msg:
            info_surf = hint_font.render(info_msg, True, (180, 230, 180))
            screen.blit(info_surf, (60, C.SCREEN_H - 110))

    running = True
    while running:
        dt = clock.tick(C.FPS) / 1000.0

        # --- BLE イベントを drain して状態遷移 ---
        if bridge is not None:
            while True:
                try:
                    ev: BridgeEvent = bridge.events.get_nowait()
                except Exception:
                    break
                _handle_bridge_event(ev, devices)
                if ev.kind == "scan_done" and state == _S_SCANNING:
                    state = _S_DEVICE_SELECT
                    if not devices:
                        info_msg = "デバイスが見つかりませんでした。もう一度試すか、デモ走行を選んでください。"
                        state = _S_TITLE
                elif ev.kind == "connected" and state == _S_CONNECTING:
                    connect_features.clear()
                    connect_features.update(ev.payload.get("features", {}))
                    state = _S_MODE_SELECT
                    info_msg = None
                elif ev.kind == "error":
                    error_msg = f"BLEエラー: {ev.payload}"
                    if state in (_S_CONNECTING, _S_SCANNING):
                        state = _S_TITLE
                elif ev.kind == "disconnected" and state in (_S_CONNECTING, _S_MODE_SELECT):
                    error_msg = "デバイスが切断されました"
                    state = _S_TITLE

        # --- 入力 ---
        mouse_pos = D.mouse_pos()
        click_consumed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if state == _S_TITLE:
                    running = False
                elif state in (_S_DEVICE_SELECT, _S_MODE_SELECT):
                    state = _S_TITLE
                    error_msg = None
                    info_msg = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_consumed = True  # 後段で位置判定

        # --- 描画 ---
        items = _items_for_state()
        if state == _S_TITLE:
            _draw_header("メニュー")
            rects = _draw_items(items, mouse_pos)
            _draw_footer("マウスで選択 / ESC で終了")
        elif state == _S_SCANNING:
            _draw_header("BLEデバイスをスキャン中...", "数秒お待ちください")
            rects = []
            _draw_footer("ESC でキャンセル")
            # スキャン中のプログレスバー風アニメ
            t_ms = pygame.time.get_ticks()
            x = 60 + (t_ms // 4) % (C.SCREEN_W - 240)
            pygame.draw.rect(screen, (80, 120, 180), (60, 280, C.SCREEN_W - 120, 6))
            pygame.draw.rect(screen, (200, 230, 255), (x, 278, 180, 10))
        elif state == _S_DEVICE_SELECT:
            _draw_header("デバイスを選択", f"{len(devices)} 件検出")
            rects = _draw_items(items, mouse_pos)
            _draw_footer("マウスで選択 / ESC で戻る")
        elif state == _S_CONNECTING:
            assert selected_device is not None
            _draw_header("接続中...", selected_device.name)
            rects = []
            _draw_footer("")
        elif state == _S_MODE_SELECT:
            assert selected_device is not None
            _draw_header("モードを選択", f"{selected_device.name}")
            rects = _draw_items(items, mouse_pos)
            _draw_footer("マウスで選択 / ESC で戻る  (無効モードはデバイスが対応していません)")
        else:
            rects = []

        D.present()

        # --- クリック判定（描画後、レイアウトが固まってから） ---
        if click_consumed and rects:
            for rect, item in zip(rects, items):
                if not (item.enabled and rect.collidepoint(mouse_pos)):
                    continue
                # 状態ごとの遷移処理
                if state == _S_TITLE:
                    if item.payload == "demo":
                        result_source = ConstantSpeedSource()
                        state = _S_DONE
                        running = False
                    else:
                        # BLE 検索
                        devices.clear()
                        error_msg = None
                        info_msg = None
                        state = _S_SCANNING
                        assert bridge is not None
                        bridge.start_scan(timeout_s=6.0)
                elif state == _S_DEVICE_SELECT:
                    if item.payload == "back":
                        state = _S_TITLE
                    else:
                        selected_device = item.payload  # type: ignore[assignment]
                        state = _S_CONNECTING
                        assert bridge is not None and selected_device is not None
                        # プロファイル（CSC/CPS）は接続後の service discovery で自動判定
                        bridge.connect(selected_device.address)
                elif state == _S_MODE_SELECT:
                    if item.payload == "back":
                        assert bridge is not None
                        bridge.disconnect()
                        state = _S_TITLE
                    else:
                        mode: Mode = item.payload  # type: ignore[assignment]
                        result_source = BleSpeedSource(bridge, mode)
                        state = _S_DONE
                        running = False
                break

    # --- 結果 ---
    if result_source is None:
        # ESC で終了された場合
        result_source = ConstantSpeedSource(0.0)  # 速度0 → 即終了とみなされる用ダミー

    if isinstance(result_source, BleSpeedSource):
        def cleanup() -> None:
            try:
                if bridge is not None:
                    bridge.disconnect()
                    bridge.close()
            except Exception:
                pass
        return result_source, cleanup
    else:
        # demo or ESC: bridge はもう不要
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass
        return result_source, (lambda: None)


def _handle_bridge_event(
    ev: BridgeEvent, devices: dict[str, DeviceCandidate]
) -> None:
    if ev.kind == "scan_result":
        d: DeviceCandidate = ev.payload
        devices[d.address] = d
