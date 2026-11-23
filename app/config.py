from pathlib import Path

SPEC = 'survey-2026.2'
EXAMPLES = Path(__file__).resolve().parents[1] / 'sample_data'
PORT = 18473
MAX_BYTES = 350_000
CHOICES = {'direct': '直达', 'transfer': '换乘', 'other': '其他'}
# 新问卷把换乘细分为公交、轨道；旧问卷的 transfer 保留为「类型未补」，不猜成任一类型。
TRANSFER_TYPES = ('transfer', 'transfer_bus', 'transfer_rail')
TRANSFER_LABELS = {'transfer': '类型未补', 'transfer_bus': '公交换乘', 'transfer_rail': '轨道换乘'}


def parent_choice(code):
    """把细分换乘码归并到调度使用的三大问项；非合法问项返回 None。"""
    if code in CHOICES:
        return code
    if code in TRANSFER_TYPES:
        return 'transfer'
    return None
