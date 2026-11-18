from nicegui import app, ui

MODES = {"light": False, "dark": True, "auto": None}
TONES = {"neutral", "success", "warning", "danger"}


class DefaultTheme:
    def __init__(self, ctx):
        self._ctx = ctx

    @property
    def mode(self) -> str:
        try:
            return self._ctx.storage.get("mode", "auto")
        except Exception:  # storage is per-user and unavailable outside a request
            return "auto"

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode!r}")
        self._ctx.storage.set("mode", mode)
        ui.dark_mode(MODES[mode])

    def card(self, title: str | None = None, actions=None):
        card = ui.card().classes("ngui-card")
        if title:
            with card:
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    ui.label(title).classes("ngui-card-title")
                    if callable(actions):
                        with ui.row().classes("items-center"):
                            actions()
        return card

    def kpi(self, label: str, value, icon: str | None = None, tone: str = "neutral"):
        tone = tone if tone in TONES else "neutral"
        with ui.card().classes("ngui-card ngui-kpi") as card:
            ui.label(label).classes("ngui-kpi-label")
            ui.label(str(value)).classes(f"ngui-kpi-value ngui-tone-{tone}")
            if icon:
                ui.icon(icon).classes(f"ngui-kpi-icon ngui-tone-{tone}")
        return card

    def page_header(self, title: str, description: str | None = None):
        with ui.column().classes("ngui-page-header") as header:
            ui.label(title).classes("ngui-page-title")
            if description:
                ui.label(description).classes("ngui-page-desc")
        return header


def setup(ctx) -> DefaultTheme:
    ui.add_css(ctx.path / "theme.css", shared=True)
    app.colors(primary="#1f2937", positive="#16a34a", warning="#b45309", negative="#dc2626")
    return DefaultTheme(ctx)
