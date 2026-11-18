from nicegui import app, ui

MODES = {"light": False, "dark": True, "auto": None}
TONES = {"neutral", "primary", "success", "warning", "danger"}
TRENDS = {"up": "arrow_drop_up", "down": "arrow_drop_down", "flat": "remove"}
# Runs while the page is still being parsed, before Quasar's own dark-mode switch, so the first paint
# already uses the dark colours instead of flashing the light background on every page load.
EARLY_DARK = {"dark": "true", "light": "false", "auto": "matchMedia('(prefers-color-scheme: dark)').matches"}


class DefaultTheme:
    def __init__(self, ctx):
        self._ctx = ctx

    @property
    def mode(self) -> str:
        try:
            m = self._ctx.storage.get("mode", "auto")
        except Exception:  # storage is per-user and unavailable outside a request
            return "auto"
        return m if m in MODES else "auto"

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode!r}")
        if mode != self.mode:
            self._ctx.storage.set("mode", mode)
        ui.dark_mode(MODES[mode])
        ui.add_body_html(f"<script>if ({EARLY_DARK[mode]}) document.body.classList.add('body--dark')</script>")

    def card(self, title: str | None = None, actions=None, meta: str | None = None):
        card = ui.card().classes("ngui-card")
        if title:
            with card:
                with ui.row().classes("ngui-card-head items-center justify-between no-wrap"):
                    ui.label(title).classes("ngui-card-title")
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        if meta:
                            ui.label(meta).classes("ngui-card-meta")
                        if callable(actions):
                            actions()
        return card

    def kpi(self, label: str, value, icon: str | None = None, tone: str = "neutral",
            delta: str | None = None, trend: str | None = None):
        tone = tone if tone in TONES else "neutral"
        with ui.card().classes("ngui-card ngui-kpi") as card:
            ui.label(label).classes("ngui-kpi-label")
            ui.label(str(value)).classes(f"ngui-kpi-value ngui-tone-{tone}")
            if icon:
                ui.icon(icon).classes("ngui-kpi-icon")
            if delta:
                trend_class = f" ngui-trend-{trend}" if trend in TRENDS else ""
                with ui.row().classes(f"ngui-kpi-delta items-center gap-0 no-wrap{trend_class}"):
                    if trend in TRENDS:
                        ui.icon(TRENDS[trend]).classes("text-base")
                    ui.label(delta)
        return card

    def page_header(self, title: str, description: str | None = None, actions=None):
        with ui.row().classes("ngui-page-header items-end justify-between no-wrap") as header:
            with ui.column().classes("gap-1"):
                ui.label(title).classes("ngui-page-title")
                if description:
                    ui.label(description).classes("ngui-page-desc")
            if callable(actions):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    actions()
        return header


def setup(ctx) -> DefaultTheme:
    ui.add_css(ctx.path / "theme.css", shared=True)
    app.colors(primary="#111827", positive="#16a34a", warning="#d97706", negative="#dc2626")
    # one look for every plugin's inputs, buttons and tables
    for element in (ui.input, ui.select, ui.number, ui.textarea):
        element.default_props("outlined dense")
    ui.button.default_props("unelevated no-caps")
    ui.table.default_props("flat bordered dense")
    return DefaultTheme(ctx)
