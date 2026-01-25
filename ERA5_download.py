import cdsapi
import os
import concurrent.futures
import threading
import time
from itertools import cycle
import socket
import urllib3
import json
import hashlib

# 禁用代理并设置超时

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["NO_PROXY"] = "*"


# 配置urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 线程锁，避免并发下载时的冲突
download_lock = threading.Lock()
progress_lock = threading.Lock()

# 下载状态记录文件
PROGRESS_FILE = "download_progress.json"


def load_progress():
    """加载下载进度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress_data):
    """保存下载进度"""
    with progress_lock:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)


def get_task_id(year, month, var_name):
    """生成任务唯一标识"""
    return f"{year}_{month:02d}_{var_name}"


def is_task_completed(task_id, filename):
    """检查任务是否已完成"""
    progress = load_progress()
    return progress.get(task_id, {}).get("status") == "completed" and os.path.exists(
        filename
    )


def mark_task_status(task_id, status, filename=None, error_msg=None):
    """标记任务状态"""
    progress = load_progress()
    if task_id not in progress:
        progress[task_id] = {}

    progress[task_id]["status"] = status
    progress[task_id]["timestamp"] = time.time()

    if filename:
        progress[task_id]["filename"] = filename
    if error_msg:
        progress[task_id]["error"] = error_msg

    save_progress(progress)


def print_progress_summary():
    """打印下载进度摘要"""
    progress = load_progress()
    if not progress:
        print("暂无下载进度记录")
        return

    total = len(progress)
    completed = sum(
        1 for task in progress.values() if task.get("status") == "completed"
    )
    failed = sum(1 for task in progress.values() if task.get("status") == "failed")
    downloading = sum(
        1 for task in progress.values() if task.get("status") == "downloading"
    )

    print(f"下载进度摘要:")
    print(f"  总任务数: {total}")
    print(f"  已完成: {completed}")
    print(f"  下载中: {downloading}")
    print(f"  失败: {failed}")

    if failed > 0:
        print(f"失败任务列表:")
        for task_id, task_info in progress.items():
            if task_info.get("status") == "failed":
                print(f"  - {task_id}: {task_info.get('error', '未知错误')}")


def retry_failed_tasks():
    """重试失败的任务"""
    progress = load_progress()
    failed_tasks = []

    for task_id, task_info in progress.items():
        if task_info.get("status") == "failed":
            failed_tasks.append(task_id)

    if not failed_tasks:
        print("没有失败的任务需要重试")
        return []

    print(f"发现 {len(failed_tasks)} 个失败的任务，准备重试")
    return failed_tasks


# 从clients.txt读取API密钥
api_keys = []
with open("clients.txt", "r") as f:
    for line_num, line in enumerate(f, 1):
        if line.strip():  # 跳过空行
            parts = [part.strip() for part in line.strip().split("\t") if part.strip()]
            print(f"第{line_num}行内容: {line.strip()}")
            print(f"分割后部分: {parts}")
            if len(parts) >= 2:
                api_key = parts[1]  # 第二列是API密钥
                api_keys.append(api_key)
                print(f"添加API密钥: {api_key[:8]}...")
            else:
                print(f"第{line_num}行格式不正确，跳过")

print(f"总共读取到 {len(api_keys)} 个API密钥:")
for i, key in enumerate(api_keys, 1):
    print(f"  {i}. {key[:8]}...")


def download_era5_data(
    year, download_dir, variables, month=None, api_key=None, max_retries=3
):
    """下载ERA5数据，使用指定的API密钥，支持断点续传"""
    dataset = "reanalysis-era5-pressure-levels"

    # 如果是按月下载
    if month is not None:
        month_str = f"{month:02d}"
        request = {
            "product_type": "reanalysis",
            "variable": variables,
            "year": str(year),
            "month": [month_str],
            "day": [
                "01",
                "02",
                "03",
                "04",
                "05",
                "06",
                "07",
                "08",
                "09",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
                "20",
                "21",
                "22",
                "23",
                "24",
                "25",
                "26",
                "27",
                "28",
                "29",
                "30",
                "31",
            ],
            "pressure_level": [
                "10",
                "20",
                "30",
                "50",
                "70",
                "100",
                "150",
                "200",
                "250",
                "300",
                "400",
                "500",
                "600",
                "700",
                "850",
                "925",
                "1000",
            ],
            "time": ["00:00", "06:00", "12:00", "18:00"],
            "grid": [2.5, 2],
            "data_format": "netcdf",
            "download_format": "unarchived",
        }

        var_name = "u" if "u_component_of_wind" in variables else "v"
        filename = os.path.join(download_dir, f"ERA5_{year}_{month_str}_{var_name}.nc")
        task_id = get_task_id(year, month, var_name)

        # 检查任务是否已完成
        if is_task_completed(task_id, filename):
            print(f"{filename} 已完成下载，跳过")
            return

        # 标记任务为下载中
        mark_task_status(task_id, "downloading", filename)
        print(
            f"正在下载 {year}年{month_str}月的{var_name}分量数据，使用API密钥 {api_key[:8]}..."
        )

        # 创建客户端时使用指定的API密钥
        client = cdsapi.Client(
            url="https://cds.climate.copernicus.eu/api",
            key=api_key,
            timeout=1800,
        )

        # 设置socket超时
        socket.setdefaulttimeout(1800)

        try:
            client.retrieve(dataset, request).download(filename)
            print(f"下载成功: {filename}")
            # 标记任务为已完成
            mark_task_status(task_id, "completed", filename)
        except Exception as e:
            print(f"下载失败: {filename}, 错误: {str(e)}")
            # 标记任务为失败
            mark_task_status(task_id, "failed", filename, str(e))
            raise


def create_download_tasks():
    """创建下载任务列表"""
    base_dir = r"wnd/"
    tasks = []

    # 添加u和v分量下载任务
    for year in range(2013, 2025):
        for month in range(1, 13):
            # 添加u分量下载任务
            u_dir = os.path.join(base_dir, "u", f"{year}/")
            if not os.path.exists(u_dir):
                os.makedirs(u_dir)
            tasks.append((year, u_dir, ["u_component_of_wind"], month))
            # 添加v分量下载任务
            v_dir = os.path.join(base_dir, "v", f"{year}/")
            if not os.path.exists(v_dir):
                os.makedirs(v_dir)
            tasks.append((year, v_dir, ["v_component_of_wind"], month))

    return tasks


def filter_pending_tasks(tasks):
    """过滤出待下载的任务"""
    pending_tasks = []
    skipped_count = 0

    for task in tasks:
        year, download_dir, variables, month = task
        var_name = "u" if "u_component_of_wind" in variables else "v"
        task_id = get_task_id(year, month, var_name)
        filename = os.path.join(download_dir, f"ERA5_{year}_{month:02d}_{var_name}.nc")

        if is_task_completed(task_id, filename):
            skipped_count += 1
        else:
            pending_tasks.append(task)

    print(f"跳过 {skipped_count} 个已完成的任务")
    print(f"剩余 {len(pending_tasks)} 个待下载任务")

    return pending_tasks


def download_tasks_batch(tasks):
    """批量下载任务"""
    if not tasks:
        print("没有待下载的任务")
        return

    print(f"开始并行下载 {len(tasks)} 个任务...")

    # 每批处理4个任务
    batch_size = 4
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i : i + batch_size]
        print(f"处理第 {i // batch_size + 1} 批任务，共 {len(batch)} 个任务...")

        # 为当前批次的每个任务分配API密钥
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            for j, task in enumerate(batch):
                # 轮换使用API密钥
                api_key = api_keys[j % len(api_keys)]
                print(f"任务 {j + 1} 分配API密钥: {api_key[:8]}...")
                # 使用lambda函数来确保参数正确传递
                future = executor.submit(
                    lambda args: download_era5_data(*args),
                    (task[0], task[1], task[2], task[3], api_key),
                )
                futures.append(future)

            # 等待当前批次完成
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"任务执行失败: {e}")

        # 如果不是最后一批，等待10秒再处理下一批
        if i + batch_size < len(tasks):
            print("等待10秒后处理下一批...")
            time.sleep(10)


if __name__ == "__main__":
    # 打印当前进度
    print("=== 当前下载进度 ===")
    print_progress_summary()
    print()

    # 创建和过滤任务
    all_tasks = create_download_tasks()
    pending_tasks = filter_pending_tasks(all_tasks)

    # 下载待处理任务
    download_tasks_batch(pending_tasks)

    print("\n=== 最终下载进度 ===")
    print_progress_summary()
    print("所有下载任务完成！")
