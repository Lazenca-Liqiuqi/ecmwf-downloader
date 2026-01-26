"""
ECMWF Downloader TUI 启动入口

执行 `python -m src.ui` 或 `python src/ui/__main__.py` 启动应用。
"""

from pathlib import Path

from src.ui.app import create_app


def main():
    """主函数"""
    # 配置文件路径
    config_path = Path("config/default_config.yaml")
    accounts_path = Path("config/accounts.yaml")
    progress_path = Path("data/download_progress.json")

    # 创建并运行应用
    app = create_app(
        config_path=config_path,
        accounts_path=accounts_path,
        progress_path=progress_path,
    )

    app.run()


if __name__ == "__main__":
    main()
