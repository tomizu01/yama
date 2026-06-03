"""レース画面（フェーズ1: 走行 / フェーズ2: BLE / フェーズ3: ステージ進行）。"""

import random

import pygame

from game import config as C
from game import stages as S
from game.assets import Assets
from game.menu import run_setup
from game.obstacles import ObstacleField
from game.player import Player
from game.speed_source import ConstantSpeedSource, SpeedSource


class Race:
    """レースの状態と更新・描画。run() からもテストハーネスからも使う。

    distance_m は障害物の描画/生成に使う「視覚距離」で、`VISUAL_SPEED_FACTOR` 倍
    された値（=見た目のスピード感）。一方 real_distance_m は実速度をそのまま積分
    した値で、ステージのゴール判定・HUD表示に使う。
    """

    def __init__(self, assets: Assets, speed_source: SpeedSource,
                 stage: S.Stage | None = None,
                 rng: random.Random | None = None) -> None:
        self.assets = assets
        self.speed_source = speed_source
        self.stage = stage
        self.player = Player()
        self.field = ObstacleField(rng)
        self.distance_m = 0.0          # 視覚距離（障害物の生成・位置に使う）
        self.real_distance_m = 0.0     # 実距離（ステージ進行・HUD表示に使う）
        self.elapsed_s = 0.0           # ステージ経過時間
        self.speed_mult = 1.0          # 衝突ペナルティ（1.0 = 通常）
        self.hit_timer = 0.0           # "HIT!" 表示の残り時間
        self.flash_timer = 0.0         # 画面フラッシュの残り時間

    @property
    def effective_kmh(self) -> float:
        return self.speed_source.speed_kmh * self.speed_mult

    @property
    def cleared(self) -> bool:
        return self.stage is not None and self.real_distance_m >= self.stage.distance_m

    def update(self, dt: float, mouse_x: float) -> None:
        self.speed_source.update(dt)

        # ペナルティの回復
        self.speed_mult = min(1.0, self.speed_mult + C.HIT_RECOVERY_PER_S * dt)
        self.hit_timer = max(0.0, self.hit_timer - dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)

        # 前進
        real_v_ms = self.effective_kmh / 3.6
        self.real_distance_m += real_v_ms * dt
        d_prev = self.distance_m
        self.distance_m += real_v_ms * C.VISUAL_SPEED_FACTOR * dt
        self.elapsed_s += dt

        # 左右移動
        self.player.update(dt, mouse_x)

        # 障害物の更新と衝突
        hits = self.field.update(d_prev, self.distance_m, self.player.u)
        if hits:
            self.speed_mult = C.HIT_SPEED_MULT
            self.hit_timer = 1.0
            self.flash_timer = 0.25

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.assets.bg, (0, 0))
        self.field.draw(surface, self.assets, self.distance_m)
        self.player.draw(surface, self.assets)
        self._draw_hud(surface)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        font = self.assets.hud_font
        lines: list[tuple[str, tuple[int, int, int]]] = [
            (f"SPEED {self.effective_kmh:5.1f} km/h", (255, 255, 255)),
        ]
        if self.stage is not None:
            remain = max(0.0, self.stage.distance_m - self.real_distance_m)
            time_color = (255, 220, 80) if self.elapsed_s > self.stage.norma_s else (255, 255, 255)
            lines.append((f"DIST  {self.real_distance_m:6.0f} m", (255, 255, 255)))
            lines.append((f"GOAL  {remain:6.0f} m", (255, 255, 255)))
            lines.append((f"TIME  {S.format_mmss(self.elapsed_s)}", time_color))
            lines.append((f"NORMA {S.format_mmss(self.stage.norma_s)}", (180, 220, 255)))
        else:
            lines.append((f"DIST  {self.real_distance_m:6.0f} m", (255, 255, 255)))

        cad = self.speed_source.cadence_rpm
        pw = self.speed_source.power_w
        if cad is not None:
            lines.append((f"CAD   {cad:5.0f} rpm", (255, 255, 255)))
        if pw is not None:
            lines.append((f"POWER {pw:5.0f} W", (255, 255, 255)))
        lines.append((f"MODE  {self.speed_source.mode_label}", (200, 200, 200)))

        for i, (text, color) in enumerate(lines):
            y = 16 + i * 44
            surface.blit(font.render(text, True, (0, 0, 0)), (22, y + 2))
            surface.blit(font.render(text, True, color), (20, y))

        if self.stage is not None:
            jp_font = self.assets.jp_hud_font
            stage_label = f"STAGE {self.stage.index}/{self.stage.total}  {self.stage.label}"
            label_surf = jp_font.render(stage_label, True, (255, 255, 255))
            label_bg = jp_font.render(stage_label, True, (0, 0, 0))
            x = C.SCREEN_W - label_surf.get_width() - 20
            surface.blit(label_bg, (x + 2, 18))
            surface.blit(label_surf, (x, 16))

        if self.hit_timer > 0:
            msg = self.assets.big_font.render("HIT!", True, (255, 60, 40))
            rect = msg.get_rect(center=(C.VP_X, 320))
            surface.blit(msg, rect)

        if self.flash_timer > 0:
            flash = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
            flash.fill((255, 0, 0))
            flash.set_alpha(70)
            surface.blit(flash, (0, 0))


# --- 日本語フォント（Windows優先） ---
_JP_FONTS = "yugothicui,yugothic,meiryo,msgothic,consolas"


def _make_fonts() -> dict[str, pygame.font.Font]:
    return {
        "title": pygame.font.SysFont(_JP_FONTS, 72, bold=True),
        "big": pygame.font.SysFont(_JP_FONTS, 56, bold=True),
        "mid": pygame.font.SysFont(_JP_FONTS, 36, bold=True),
        "small": pygame.font.SysFont(_JP_FONTS, 28),
    }


def _wait_click_or_quit(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    speed_source: SpeedSource,
    draw_fn,
) -> bool:
    """画面を描画しつつ、マウスクリックか QUIT/ESC を待つ。

    描画は draw_fn(screen) を毎フレーム呼ぶ。speed_source.update() も継続して呼ぶ
    （BLE 切断検出やデモ走行の速度調整キーを生かすため）。

    Returns: True=クリックで先へ進む / False=ユーザーが終了を選んだ
    """
    while True:
        dt = clock.tick(C.FPS) / 1000.0
        speed_source.update(dt)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return True
            if event.type == pygame.KEYDOWN and isinstance(speed_source, ConstantSpeedSource):
                if event.key == pygame.K_UP:
                    speed_source.adjust(+C.DEBUG_SPEED_STEP)
                elif event.key == pygame.K_DOWN:
                    speed_source.adjust(-C.DEBUG_SPEED_STEP)
        draw_fn(screen)
        pygame.display.flip()


def _draw_stage_start(
    screen: pygame.Surface, fonts: dict, stage: S.Stage, bg: pygame.Surface
) -> None:
    screen.blit(bg, (0, 0))
    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    cx = C.SCREEN_W // 2

    def _center(text: str, font: pygame.font.Font, y: int, color=(255, 255, 255)) -> None:
        surf = font.render(text, True, color)
        screen.blit(surf, (cx - surf.get_width() // 2, y))

    _center(f"STAGE {stage.index} / {stage.total}", fonts["mid"], 200, (200, 220, 255))
    _center(stage.label, fonts["title"], 270)
    _center(f"距離  {stage.distance_m:,.0f} m", fonts["big"], 430, (255, 230, 120))
    _center(f"ノルマ  {S.format_mmss(stage.norma_s)}  ({S.NORMA_KMH:.0f} km/h)",
            fonts["mid"], 540, (180, 220, 255))
    _center("クリックでスタート", fonts["mid"], 800, (220, 220, 220))


def _draw_stage_clear(
    screen: pygame.Surface, fonts: dict, stage: S.Stage,
    elapsed_s: float, distance_m: float, bg: pygame.Surface, is_final: bool,
) -> None:
    screen.blit(bg, (0, 0))
    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    cx = C.SCREEN_W // 2
    won = elapsed_s <= stage.norma_s

    def _center(text: str, font: pygame.font.Font, y: int, color=(255, 255, 255)) -> None:
        surf = font.render(text, True, color)
        screen.blit(surf, (cx - surf.get_width() // 2, y))

    _center(f"STAGE {stage.index} / {stage.total}  CLEAR", fonts["mid"], 150, (200, 220, 255))
    _center(stage.label, fonts["big"], 220)

    _center(f"進んだ距離  {distance_m:,.0f} m", fonts["mid"], 380)
    _center(f"所要時間    {S.format_mmss(elapsed_s)}", fonts["mid"], 440)
    _center(f"ノルマ      {S.format_mmss(stage.norma_s)}", fonts["mid"], 500, (180, 200, 220))

    if won:
        _center("WIN!", fonts["title"], 600, (120, 255, 140))
    else:
        _center("LOSE...", fonts["title"], 600, (255, 120, 120))

    hint = "クリックで終了" if is_final else "クリックで次のステージへ"
    _center(hint, fonts["mid"], 820, (220, 220, 220))


def run() -> None:
    pygame.init()
    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.SCALED)
    pygame.display.set_caption("路線Rider")
    clock = pygame.time.Clock()

    # フェーズ2: 起動時のセットアップ画面でBLE/デモを選択
    speed_source, cleanup = run_setup(screen, clock)
    assets = Assets()
    fonts = _make_fonts()

    # フェーズ3: ステージ一覧
    stations = S.load_stations(S.default_csv_path())
    stages_list = S.build_stages(stations)

    quit_game = False
    try:
        for stage in stages_list:
            # --- ステージ開始画面 ---
            if not _wait_click_or_quit(
                screen, clock, speed_source,
                lambda sc, st=stage: _draw_stage_start(sc, fonts, st, assets.bg),
            ):
                quit_game = True
                break

            # --- レース本体 ---
            race = Race(assets, speed_source, stage=stage)
            stage_finished = False
            while not stage_finished:
                dt = min(clock.tick(C.FPS) / 1000.0, 0.05)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        quit_game = True
                        stage_finished = True
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            quit_game = True
                            stage_finished = True
                        elif isinstance(speed_source, ConstantSpeedSource):
                            if event.key == pygame.K_UP:
                                speed_source.adjust(+C.DEBUG_SPEED_STEP)
                            elif event.key == pygame.K_DOWN:
                                speed_source.adjust(-C.DEBUG_SPEED_STEP)

                mouse_x, _ = pygame.mouse.get_pos()
                race.update(dt, mouse_x)
                race.draw(screen)
                pygame.display.flip()

                if race.cleared:
                    stage_finished = True

            if quit_game:
                break

            # --- ステージクリア画面 ---
            is_final = stage.index == stage.total
            if not _wait_click_or_quit(
                screen, clock, speed_source,
                lambda sc, st=stage, e=race.elapsed_s, d=race.real_distance_m,
                fin=is_final: _draw_stage_clear(sc, fonts, st, e, d, assets.bg, fin),
            ):
                quit_game = True
                break
    finally:
        speed_source.close()
        cleanup()
        pygame.quit()
