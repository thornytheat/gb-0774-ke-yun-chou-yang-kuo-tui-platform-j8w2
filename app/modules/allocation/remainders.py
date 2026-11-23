from fractions import Fraction

from app.config import CHOICES, TRANSFER_TYPES
from app.errors import SurveyProblem


def largest_remainders(values, total, keys=None):
    keys = tuple(keys or CHOICES)
    exact = {key:Fraction(values[key]) for key in keys}
    if any(value < 0 for value in exact.values()) or sum(exact.values()) != total:
        raise SurveyProblem('BAD_QUOTA', '配额与分层人口不一致')
    floors = {key:int(val) for key,val in exact.items()}
    order = sorted(keys, key=lambda key: exact[key]-floors[key], reverse=True)
    winners = order[:total-sum(floors.values())]
    result = {key:floor+int(key in winners) for key,floor in floors.items()}
    return dict(integers=result, floors=floors, winners=winners,
                remainders={key:str(exact[key]-floors[key]) for key in floors})


def split_transfer(quotas, total):
    """把换乘整数人数按同套最大余数规则分到公交、轨道、类型未补，合计仍为换乘总数。

    各类型精确配额是分数（合计为换乘精确配额），这里分配的是换乘整数总数，
    因此不做分数合计等于整数的校验；分数守恒由对账页 quota_delta 留档核对。
    """
    exact = {key:Fraction(quotas[key]) for key in TRANSFER_TYPES}
    if any(value < 0 for value in exact.values()):
        raise SurveyProblem('BAD_QUOTA', '换乘类型配额不能为负')
    floors = {key:int(val) for key,val in exact.items()}
    order = sorted(TRANSFER_TYPES, key=lambda key: exact[key]-floors[key], reverse=True)
    winners = order[:total-sum(floors.values())]
    integers = {key:floors[key]+int(key in winners) for key in TRANSFER_TYPES}
    return dict(integers=integers, floors=floors, winners=winners,
                remainders={key:str(exact[key]-floors[key]) for key in floors})
