from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # StarRocks
    starrocks_host: str = "localhost"
    starrocks_port: int = 9030
    starrocks_user: str = "root"
    starrocks_password: str = ""
    starrocks_database: str = "hl_customer_outbound"

    # NebulaGraph
    nebula_host: str = "localhost"
    nebula_port: int = 9669
    nebula_user: str = "root"
    nebula_password: str = "nebula"
    nebula_space: str = "stockout"

    # LLM (Ollama)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.1:8b"
    
    # Ask budgets (ms)
    ask_total_timeout_ms: int = 10000
    ask_thorough_timeout_ms: int = 30000
    ask_max_iterations: int = 12
    ask_per_query_timeout_ms: int = 5000

    # Diagnosis thresholds (PHANTOM: distinct_fsns >= threshold; GENUINE: distinct_bins >= threshold)
    diagnosis_window_days: int = 1
    phantom_fsn_threshold: int = 3
    stockout_bin_threshold: int = 2

    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
