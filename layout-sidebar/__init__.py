import functools
import inspect
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from nicegui import ui

SLOTS = ("nav", "header", "main", "statusbar", "user")
MODES = ("light", "dark", "auto")
MODE_ICONS = {"light": "light_mode", "dark": "dark_mode", "auto": "brightness_auto"}

CSS = """
.q-header.ngui-topbar {
  background: var(--ngui-surface) !important; color: var(--ngui-text) !important;
  border-bottom: 1px solid var(--ngui-border); padding: 8px 20px; align-items: center; gap: 6px;
}
.ngui-app-name { font-size: 1.0625rem; font-weight: 700; letter-spacing: -0.01em; }
.ngui-topbar .q-btn { color: var(--ngui-text); }
.ngui-user { border: 1px solid var(--ngui-border); }
.ngui-menu-head { padding: 10px 16px 6px; }
.ngui-menu-name { font-weight: 600; font-size: 0.875rem; }
.ngui-menu-sub { font-size: 0.75rem; color: var(--ngui-muted); }
.q-drawer:has(> .ngui-rail) { background: var(--ngui-surface) !important; border-right: 1px solid var(--ngui-border); }
.ngui-rail { gap: 4px; padding: 12px 10px; }
.ngui-nav-item {
  position: relative; display: flex; align-items: center; gap: 12px; padding: 9px 10px;
  border-radius: 8px; color: var(--ngui-muted); text-decoration: none; white-space: nowrap; overflow: hidden;
  font-size: 0.875rem;
}
.ngui-nav-item .q-icon { font-size: 1.25rem; flex: none; }
.ngui-nav-item:hover { color: var(--ngui-text); background: var(--ngui-hover); }
.ngui-nav-item.ngui-active { color: var(--ngui-text); background: var(--ngui-hover); font-weight: 600; }
.ngui-nav-item.ngui-active::before {
  content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px;
  border-radius: 3px; background: var(--ngui-primary);
}
.ngui-rail .q-separator { background: var(--ngui-border) !important; border: 0; margin: 4px 0; }
.ngui-rail-toggle { align-self: flex-start; color: var(--ngui-muted); margin-left: 4px; }
.ngui-content { width: 100%; padding: 20px 28px 28px; gap: var(--ngui-gap); }
.ngui-breadcrumb { font-size: 0.75rem; color: var(--ngui-muted); gap: 6px; }
.ngui-breadcrumb a { color: var(--ngui-muted); text-decoration: none; }
.ngui-breadcrumb .ngui-current { color: var(--ngui-text); font-weight: 600; }
.ngui-grid {
  display: grid; width: 100%; gap: var(--ngui-gap);
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
.ngui-page-link { color: inherit; text-decoration: none; }
.ngui-page-link .ngui-card:hover { border-color: var(--ngui-muted); }
.ngui-page-link .q-icon { font-size: 1.5rem; color: var(--ngui-muted); }
.ngui-error, .ngui-forbidden { color: var(--ngui-danger); }
.q-footer.ngui-statusbar {
  background: var(--ngui-surface) !important; color: var(--ngui-muted) !important;
  border-top: 1px solid var(--ngui-border); padding: 4px 16px; font-size: 0.8125rem; gap: 12px;
}
"""


@dataclass
class PageEntry:
    path: str
    title: str | Callable[[], str]
    icon: str | None = None
    permission: str | None = None


class SidebarLayout:
    def __init__(self, ctx):
        self._ctx = ctx
        self.pages: list[PageEntry] = []
        self.slots: dict[str, list[Callable[[], None]]] = {s: [] for s in SLOTS}
        self.home = PageEntry("/", lambda: ctx.t("home.title"), "home")
        ui.page("/")(self._home)

    def page(self, path: str, title, icon: str | None = None, permission: str | None = None) -> Callable:
        entry = PageEntry(path, title, icon, permission)
        self.pages.append(entry)

        if path == "/":
            self._ctx.log.warning("a page registered at '/' replaces the layout's home page")

        def decorator(fn):
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                with self.frame(entry):
                    if not self._allowed(entry):
                        self._forbidden()
                        return
                    try:
                        res = fn(*args, **kwargs)
                        if inspect.isawaitable(res):
                            await res
                    except Exception:
                        self._render_error(fn)

            ui.page(path)(wrapper)
            return fn
        return decorator

    def add(self, slot: str, builder: Callable[[], None]) -> None:
        if slot in SLOTS:
            self.slots[slot].append(builder)

    def _text(self, entry: PageEntry) -> str:
        try:
            return entry.title() if callable(entry.title) else entry.title
        except Exception:
            self._ctx.log.exception("title failed for %s", entry.path)
            return entry.path

    def _allowed(self, entry: PageEntry) -> bool:
        try:
            return not entry.permission or bool(self._ctx.role("auth").has(entry.permission))
        except Exception:
            self._ctx.log.exception("permission check failed for %s", entry.path)
            return False

    def _forbidden(self) -> None:
        ui.label(self._ctx.t("forbidden")).classes("ngui-forbidden")

    def _render_error(self, fn) -> None:
        self._ctx.log.exception("render failed: %s", getattr(fn, "__qualname__", fn))
        ui.label(self._ctx.t("error.render")).classes("ngui-error")

    def _safe(self, fn, *args, **kwargs) -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            self._render_error(fn)

    def _slot(self, name: str) -> None:
        for builder in self.slots[name]:
            self._safe(builder)

    @contextmanager
    def frame(self, entry: PageEntry):
        theme = self._ctx.role("theme")
        theme.set_mode(theme.mode)
        self._topbar(theme)
        self._rail(entry)
        with ui.column().classes("ngui-content"):
            self._breadcrumb(entry)
            yield
        if self.slots["statusbar"]:
            with ui.footer().classes("ngui-statusbar items-center"):
                self._slot("statusbar")

    def _topbar(self, theme) -> None:
        t, i18n = self._ctx.t, self._ctx.i18n
        with ui.header().classes("ngui-topbar"):
            ui.label(t("app.name")).classes("ngui-app-name")
            ui.space()
            self._slot("header")
            current = i18n.current_lang()
            with ui.button(current.upper(), icon="language", color=None).props("flat dense").classes("ngui-lang"):
                ui.tooltip(t("lang.switch"))
                with ui.menu():
                    for lang in i18n.languages():
                        item = ui.item(t(f"lang.{lang}"), on_click=lambda _, lang=lang: i18n.set_lang(lang))
                        if lang == current:
                            item.classes("text-weight-bold")
            mode = theme.mode if theme.mode in MODES else "auto"
            nxt = MODES[(MODES.index(mode) + 1) % len(MODES)]

            def cycle_theme():
                theme.set_mode(nxt)
                ui.navigate.reload()

            ui.button(icon=MODE_ICONS[mode], on_click=cycle_theme, color=None).props("flat round dense").tooltip(
                t("theme.toggle"))
            user = self._ctx.role("auth").current_user()
            with ui.button(user["name"], icon="account_circle", color=None).props("flat dense icon-right=expand_more").classes(
                    "ngui-user q-px-sm"):
                with ui.menu():
                    with ui.column().classes("ngui-menu-head gap-0"):
                        ui.label(user["name"]).classes("ngui-menu-name")
                        ui.label(", ".join(user.get("roles", [])) or "-").classes("ngui-menu-sub")
                    self._slot("user")

    def _rail(self, entry: PageEntry) -> None:
        store = self._ctx.storage
        expanded = bool(store.get("drawer.expanded", False))
        drawer = ui.left_drawer(value=True).classes("ngui-rail")
        drawer.props.update({"mini": not expanded, "mini-width": 64, "width": 232, "breakpoint": 0})
        tips = []
        with drawer:
            for page in [self.home, *filter(self._allowed, self.pages)]:
                title = self._text(page)
                active = " ngui-active" if page.path == entry.path else ""
                with ui.link(target=page.path).classes("ngui-nav-item" + active):
                    ui.icon(page.icon or "article")
                    ui.label(title).classes("q-mini-drawer-hide")
                    tip = ui.tooltip(title).props('anchor="center right" self="center left"')
                    tip.props["disable"] = expanded
                    tips.append(tip)
            self._slot("nav")
            ui.space()
            ui.separator()
            toggle = ui.button(icon="chevron_left" if expanded else "chevron_right", color=None)
            toggle.props("flat round dense").classes("ngui-rail-toggle")
            with toggle:
                toggle_tip = ui.tooltip(self._ctx.t("menu.collapse" if expanded else "menu.expand"))

        def on_toggle():
            now = bool(drawer.props["mini"])  # was mini, so now expanded
            drawer.props["mini"] = not now
            toggle.props["icon"] = "chevron_left" if now else "chevron_right"
            toggle_tip.text = self._ctx.t("menu.collapse" if now else "menu.expand")
            for tip in tips:
                tip.props["disable"] = now
            store.set("drawer.expanded", now)

        toggle.on_click(on_toggle)

    def _breadcrumb(self, entry: PageEntry) -> None:
        with ui.row().classes("ngui-breadcrumb items-center no-wrap"):
            ui.icon("home")
            ui.link(self._ctx.t("home.title"), "/").classes("ngui-current" if entry is self.home else "")
            if entry is not self.home:
                ui.label("›")
                ui.label(self._text(entry)).classes("ngui-current")

    def _home(self) -> None:
        t, theme = self._ctx.t, self._ctx.role("theme")
        with self.frame(self.home):
            theme.page_header(t("home.title"), t("home.description"))
            pages = [] if self.slots["main"] else [p for p in self.pages if self._allowed(p)]
            if self.slots["main"] or pages:
                with ui.element("div").classes("ngui-grid"):
                    self._slot("main")
                    for p in pages:
                        with ui.link(target=p.path).classes("ngui-page-link"):
                            with theme.card().classes("w-full"):
                                ui.icon(p.icon or "article")
                                ui.label(self._text(p)).classes("ngui-card-title")


def setup(ctx) -> SidebarLayout:
    for role in ("storage", "auth", "theme"):  # a missing role breaks layout, so recovery serves every path
        ctx.role(role)
    ui.add_css(CSS, shared=True)
    return SidebarLayout(ctx)
