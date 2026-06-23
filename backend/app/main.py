from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fund Label Engine",
        description="Explainable fund label calculation engine.",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

