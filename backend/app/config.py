"""应用配置：从项目根目录的 .env 读取。

key 只在后端持有，绝不进浏览器。这里只暴露「配置项是否已填」，
不向外打印 key 值本身。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/ 的上一级），.env 和 SQLite 都放这里
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== 通义千问 / DashScope =====
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_vl_model: str = "qwen-vl-plus"
    qwen_text_model: str = "qwen-plus"

    # ===== 本地 Ollama =====
    vlm_provider: str = "dashscope"  # dashscope / ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_vl_model: str = "qwen3-vl:8b"

    # ===== 数据库 =====
    db_path: Path = PROJECT_ROOT / "mistakegenie.db"

    # ===== 本地文件存储 =====
    # 题目配图等本地文件根目录；DB 里只存相对此目录的路径
    media_dir: Path = PROJECT_ROOT / "media"

    def config_presence(self) -> dict[str, bool]:
        """报告各关键配置项是否已填（不暴露 key 值本身）。"""
        return {
            "DASHSCOPE_API_KEY": bool(self.dashscope_api_key.strip()),
            "DASHSCOPE_BASE_URL": bool(self.dashscope_base_url.strip()),
            "QWEN_VL_MODEL": bool(self.qwen_vl_model.strip()),
            "QWEN_TEXT_MODEL": bool(self.qwen_text_model.strip()),
            "VLM_PROVIDER": bool(self.vlm_provider.strip()),
            "OLLAMA_BASE_URL": bool(self.ollama_base_url.strip()),
            "OLLAMA_VL_MODEL": bool(self.ollama_vl_model.strip()),
        }


settings = Settings()
