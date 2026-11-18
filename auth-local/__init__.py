class LocalAuth:
    def __init__(self, ctx):
        self._ctx = ctx

    def current_user(self) -> dict:
        return {"id": "local", "name": self._ctx.t("user.name"), "roles": ["admin"]}

    def has(self, permission: str) -> bool:
        return True


def setup(ctx) -> LocalAuth:
    return LocalAuth(ctx)
