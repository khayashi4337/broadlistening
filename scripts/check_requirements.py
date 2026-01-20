#!/usr/bin/env python3
"""
Broadlistening システム要件診断ツール

使用方法:
    python scripts/check_requirements.py

このスクリプトは以下をチェックします:
- CPU情報（コア数、モデル）
- メモリ容量
- GPU情報（NVIDIA GPU検出）
- ディスク空き容量
- Docker/Docker Compose
- 推奨構成の提案
"""

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path


# =============================================================================
# 定数
# =============================================================================

# 最小要件
MIN_RAM_GB = 8
MIN_DISK_GB = 10
MIN_CPU_CORES = 2

# 推奨要件
REC_RAM_GB = 16
REC_DISK_GB = 20
REC_CPU_CORES = 4

# GPU要件
MIN_VRAM_GB = 6
REC_VRAM_GB = 8

# 処理時間の目安（秒/件）
ESTIMATE_GPU_SEC_PER_ITEM = 2
ESTIMATE_CPU_SEC_PER_ITEM = 30
ESTIMATE_CPU_FAST_SEC_PER_ITEM = 15  # 高性能CPU


# =============================================================================
# カラー出力
# =============================================================================

class Colors:
    """ターミナルカラー"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

    @classmethod
    def disable(cls):
        """カラーを無効化（Windows CMD対応）"""
        cls.GREEN = cls.YELLOW = cls.RED = cls.BLUE = cls.BOLD = cls.END = ''


# Windowsの場合の対応
if platform.system() == 'Windows':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        Colors.disable()

    # 標準出力のエンコーディングをUTF-8に設定
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
    except Exception:
        pass


def ok(msg: str) -> str:
    return f"{Colors.GREEN}✓{Colors.END} {msg}"

def warn(msg: str) -> str:
    return f"{Colors.YELLOW}⚠{Colors.END} {msg}"

def fail(msg: str) -> str:
    return f"{Colors.RED}✗{Colors.END} {msg}"

def info(msg: str) -> str:
    return f"{Colors.BLUE}ℹ{Colors.END} {msg}"

def bold(msg: str) -> str:
    return f"{Colors.BOLD}{msg}{Colors.END}"


# =============================================================================
# システム情報取得
# =============================================================================

def get_cpu_info() -> dict:
    """CPU情報を取得"""
    info = {
        'cores': os.cpu_count() or 0,
        'model': 'Unknown',
    }

    try:
        if platform.system() == 'Windows':
            # Windows
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'name'],
                capture_output=True, text=True, timeout=10
            )
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip() and l.strip() != 'Name']
            if lines:
                info['model'] = lines[0]
        elif platform.system() == 'Darwin':
            # macOS
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True, text=True, timeout=10
            )
            info['model'] = result.stdout.strip()
        else:
            # Linux
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        info['model'] = line.split(':')[1].strip()
                        break
    except Exception:
        pass

    return info


def get_memory_info() -> dict:
    """メモリ情報を取得"""
    info: dict = {'total_gb': 0.0, 'available_gb': 0.0}

    try:
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory'],
                capture_output=True, text=True, timeout=10
            )
            # WMICの出力は複数の空行を含む可能性があるため、空でない行を探す
            for line in result.stdout.strip().split('\n'):
                values = line.split()
                # 数値が2つ含まれる行を探す
                if len(values) >= 2 and values[0].isdigit() and values[1].isdigit():
                    # 出力順: FreePhysicalMemory, TotalVisibleMemorySize (KB単位)
                    info['available_gb'] = int(values[0]) / (1024 * 1024)
                    info['total_gb'] = int(values[1]) / (1024 * 1024)
                    break
        elif platform.system() == 'Darwin':
            # macOS
            result = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True, text=True, timeout=10
            )
            info['total_gb'] = int(result.stdout.strip()) / (1024**3)
            # macOS doesn't have a simple way to get available memory
            info['available_gb'] = info['total_gb'] * 0.7  # 推定
        else:
            # Linux
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        info['total_gb'] = int(line.split()[1]) / (1024 * 1024)
                    elif 'MemAvailable' in line:
                        info['available_gb'] = int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass

    return info


def get_gpu_info() -> dict:
    """GPU情報を取得（NVIDIA）"""
    info = {
        'available': False,
        'name': None,
        'vram_gb': 0,
        'driver_version': None,
        'cuda_version': None,
    }

    try:
        # nvidia-smi で情報取得
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) >= 3:
                info['available'] = True
                info['name'] = parts[0]
                info['vram_gb'] = int(parts[1]) / 1024
                info['driver_version'] = parts[2]

        # CUDA バージョン
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=cuda_version', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            info['cuda_version'] = result.stdout.strip()
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return info


def get_disk_info() -> dict:
    """ディスク空き容量を取得"""
    info: dict = {'free_gb': 0.0, 'total_gb': 0.0}

    try:
        # 現在のディレクトリのディスク情報
        usage = shutil.disk_usage(Path.cwd())
        info['total_gb'] = usage.total / (1024**3)
        info['free_gb'] = usage.free / (1024**3)
    except Exception:
        pass

    return info


def check_docker() -> dict:
    """Docker情報を取得"""
    info = {
        'installed': False,
        'version': None,
        'compose_installed': False,
        'compose_version': None,
        'running': False,
    }

    try:
        # Docker バージョン
        result = subprocess.run(
            ['docker', '--version'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            info['installed'] = True
            info['version'] = result.stdout.strip()

        # Docker Compose バージョン
        result = subprocess.run(
            ['docker', 'compose', 'version'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            info['compose_installed'] = True
            info['compose_version'] = result.stdout.strip()
        else:
            # 旧形式を試す
            result = subprocess.run(
                ['docker-compose', '--version'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                info['compose_installed'] = True
                info['compose_version'] = result.stdout.strip()

        # Docker デーモンが動作しているか
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True, text=True, timeout=10
        )
        info['running'] = (result.returncode == 0)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return info


# =============================================================================
# 診断ロジック
# =============================================================================

def diagnose() -> dict:
    """システム診断を実行"""
    results = {
        'cpu': get_cpu_info(),
        'memory': get_memory_info(),
        'gpu': get_gpu_info(),
        'disk': get_disk_info(),
        'docker': check_docker(),
        'recommendation': 'cpu',  # cpu or gpu
        'issues': [],
        'warnings': [],
    }

    # CPU チェック
    if results['cpu']['cores'] < MIN_CPU_CORES:
        results['issues'].append(f"CPUコア数が不足: {results['cpu']['cores']}コア (最小{MIN_CPU_CORES}コア)")
    elif results['cpu']['cores'] < REC_CPU_CORES:
        results['warnings'].append(f"CPUコア数が推奨未満: {results['cpu']['cores']}コア (推奨{REC_CPU_CORES}コア以上)")

    # メモリチェック
    if results['memory']['total_gb'] < MIN_RAM_GB:
        results['issues'].append(f"メモリ不足: {results['memory']['total_gb']:.1f}GB (最小{MIN_RAM_GB}GB)")
    elif results['memory']['total_gb'] < REC_RAM_GB:
        results['warnings'].append(f"メモリが推奨未満: {results['memory']['total_gb']:.1f}GB (推奨{REC_RAM_GB}GB以上)")

    # ディスクチェック
    if results['disk']['free_gb'] < MIN_DISK_GB:
        results['issues'].append(f"ディスク空き容量不足: {results['disk']['free_gb']:.1f}GB (最小{MIN_DISK_GB}GB)")
    elif results['disk']['free_gb'] < REC_DISK_GB:
        results['warnings'].append(f"ディスク空きが推奨未満: {results['disk']['free_gb']:.1f}GB (推奨{REC_DISK_GB}GB以上)")

    # Dockerチェック
    if not results['docker']['installed']:
        results['issues'].append("Dockerがインストールされていません")
    elif not results['docker']['compose_installed']:
        results['issues'].append("Docker Composeがインストールされていません")
    elif not results['docker']['running']:
        results['warnings'].append("Dockerデーモンが起動していません")

    # GPU チェック & 推奨構成決定
    if results['gpu']['available']:
        if results['gpu']['vram_gb'] >= MIN_VRAM_GB:
            results['recommendation'] = 'gpu'
            if results['gpu']['vram_gb'] < REC_VRAM_GB:
                results['warnings'].append(f"VRAM推奨未満: {results['gpu']['vram_gb']:.1f}GB (推奨{REC_VRAM_GB}GB以上)")
        else:
            results['warnings'].append(f"VRAM不足でGPU利用不可: {results['gpu']['vram_gb']:.1f}GB (最小{MIN_VRAM_GB}GB)")

    return results


def estimate_processing_time(num_items: int, use_gpu: bool, fast_cpu: bool = False) -> str:
    """処理時間を推定"""
    if use_gpu:
        seconds = num_items * ESTIMATE_GPU_SEC_PER_ITEM
    elif fast_cpu:
        seconds = num_items * ESTIMATE_CPU_FAST_SEC_PER_ITEM
    else:
        seconds = num_items * ESTIMATE_CPU_SEC_PER_ITEM

    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        return f"{int(seconds / 60)}分"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}時間"


# =============================================================================
# 出力
# =============================================================================

def print_results(results: dict):
    """診断結果を出力"""
    print()
    print(bold("=" * 50))
    print(bold("   Broadlistening システム診断"))
    print(bold("=" * 50))
    print()

    # CPU
    cpu = results['cpu']
    cpu_status = ok(f"{cpu['cores']}コア") if cpu['cores'] >= MIN_CPU_CORES else fail(f"{cpu['cores']}コア")
    print(f"[CPU] {cpu['model'][:40]}...")
    print(f"      コア数: {cpu_status}")
    print()

    # メモリ
    mem = results['memory']
    if mem['total_gb'] >= REC_RAM_GB:
        mem_status = ok(f"{mem['total_gb']:.1f}GB")
    elif mem['total_gb'] >= MIN_RAM_GB:
        mem_status = warn(f"{mem['total_gb']:.1f}GB")
    else:
        mem_status = fail(f"{mem['total_gb']:.1f}GB")
    print(f"[メモリ] {mem_status} (最小{MIN_RAM_GB}GB / 推奨{REC_RAM_GB}GB)")
    print()

    # GPU
    gpu = results['gpu']
    if gpu['available']:
        if gpu['vram_gb'] >= MIN_VRAM_GB:
            gpu_status = ok(f"{gpu['name']} ({gpu['vram_gb']:.0f}GB VRAM)")
        else:
            gpu_status = warn(f"{gpu['name']} ({gpu['vram_gb']:.0f}GB VRAM - 不足)")
        print(f"[GPU] {gpu_status}")
        if gpu['driver_version']:
            print(f"      ドライバ: {gpu['driver_version']}")
    else:
        print(f"[GPU] {info('検出されませんでした（CPU版を使用）')}")
    print()

    # ディスク
    disk = results['disk']
    if disk['free_gb'] >= REC_DISK_GB:
        disk_status = ok(f"{disk['free_gb']:.1f}GB空き")
    elif disk['free_gb'] >= MIN_DISK_GB:
        disk_status = warn(f"{disk['free_gb']:.1f}GB空き")
    else:
        disk_status = fail(f"{disk['free_gb']:.1f}GB空き")
    print(f"[ディスク] {disk_status} (最小{MIN_DISK_GB}GB必要)")
    print()

    # Docker
    docker = results['docker']
    if docker['installed'] and docker['compose_installed'] and docker['running']:
        print(f"[Docker] {ok('準備完了')}")
    elif docker['installed'] and docker['compose_installed']:
        print(f"[Docker] {warn('インストール済み（デーモン未起動）')}")
    elif docker['installed']:
        print(f"[Docker] {warn('Docker Composeが必要')}")
    else:
        print(f"[Docker] {fail('未インストール')}")
    print()

    # 問題点
    if results['issues']:
        print(bold("-" * 50))
        print(fail(" 問題点（修正が必要）"))
        print(bold("-" * 50))
        for issue in results['issues']:
            print(f"  • {issue}")
        print()

    # 警告
    if results['warnings']:
        print(bold("-" * 50))
        print(warn(" 警告（動作するが改善推奨）"))
        print(bold("-" * 50))
        for warning in results['warnings']:
            print(f"  • {warning}")
        print()

    # 推奨構成
    print(bold("=" * 50))
    print(bold("   推奨構成"))
    print(bold("=" * 50))
    print()

    if results['issues']:
        print(fail("システム要件を満たしていません。上記の問題を解決してください。"))
    elif results['recommendation'] == 'gpu':
        print(ok("GPU版 (docker-compose.yml) を使用できます"))
        print()
        print("  起動コマンド:")
        print(f"  {Colors.BLUE}docker compose up -d{Colors.END}")
    else:
        print(info("CPU版 (docker-compose.cpu.yml) を使用してください"))
        print()
        print("  起動コマンド:")
        print(f"  {Colors.BLUE}docker compose -f docker-compose.cpu.yml up -d{Colors.END}")
    print()

    # 処理時間の目安
    print(bold("=" * 50))
    print(bold("   処理時間の目安"))
    print(bold("=" * 50))
    print()

    use_gpu = (results['recommendation'] == 'gpu')
    fast_cpu = (results['cpu']['cores'] >= 8)

    print(f"  {'件数':<10} {'あなたの環境':<15} {'参考: GPU版':<15}")
    print(f"  {'-'*10} {'-'*15} {'-'*15}")
    for num in [100, 500, 1000, 5000]:
        your_time = estimate_processing_time(num, use_gpu, fast_cpu)
        gpu_time = estimate_processing_time(num, True)
        print(f"  {num:<10} {your_time:<15} {gpu_time:<15}")
    print()

    if not use_gpu:
        print(info("GPU環境では処理速度が10〜20倍向上します"))
        print()

    # 次のステップ
    print(bold("=" * 50))
    print(bold("   次のステップ"))
    print(bold("=" * 50))
    print()

    if results['issues']:
        print("  1. 上記の問題を解決してください")
        print("  2. 再度このスクリプトを実行して確認")
    else:
        print("  1. 環境設定:")
        print(f"     {Colors.BLUE}cp .env.example .env{Colors.END}")
        print()
        if use_gpu:
            print("  2. 起動:")
            print(f"     {Colors.BLUE}docker compose up -d{Colors.END}")
        else:
            print("  2. 起動:")
            print(f"     {Colors.BLUE}docker compose -f docker-compose.cpu.yml up -d{Colors.END}")
        print()
        print("  3. 初期化:")
        print(f"     {Colors.BLUE}docker exec broadlistening-n8n python3 /scripts/qdrant_manager.py init{Colors.END}")
        print()
        print("  4. ベンチマーク（実測）:")
        print(f"     {Colors.BLUE}python scripts/benchmark.py{Colors.END}")
    print()


# =============================================================================
# メイン
# =============================================================================

def main():
    """メインエントリーポイント"""
    print("\nシステム情報を収集中...\n")

    results = diagnose()
    print_results(results)

    # 終了コード
    if results['issues']:
        sys.exit(1)
    elif results['warnings']:
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
