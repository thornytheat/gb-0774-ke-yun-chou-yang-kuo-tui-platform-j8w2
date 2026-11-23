from collections import Counter
from fractions import Fraction

from app.config import TRANSFER_TYPES

from .shares import bias


def review(intake, frame, weighted, allocation):
    frame_total = sum(frame['population'].values())
    input_counts = intake['totals']
    returned = frame['counts']
    line_delta = input_counts['input']-input_counts['isolated']-sum(returned.values())
    all_observed = Counter()
    strata = {}
    for name, population in frame['population'].items():
        row, calibrated = allocation['layers'][name], weighted['layers'][name]
        if row['status']=='calibrated':
            all_observed.update(calibrated['observed'])
        # 换乘分层留档：公交、轨道、类型未补三栏的精确配额与整数都要对得上换乘总数。
        transfer_quotas = {key:Fraction(calibrated['transfer_quotas'][key]) for key in TRANSFER_TYPES}
        quota_gap = str(sum(transfer_quotas.values())-Fraction(calibrated['quotas']['transfer']))
        integer_gap = sum(row['transfer']['integers'].values())-row['integers']['transfer']
        transfer_ledger = dict(
            quotas={key:str(transfer_quotas[key]) for key in TRANSFER_TYPES},
            integers=dict(row['transfer']['integers']),
            observed=dict(calibrated['transfer_observed']),
            quota_delta=quota_gap,
            integer_delta=integer_gap,
        )
        strata[name] = dict(population=population, usable=calibrated['usable'],
                            unknown=row['unobserved'], allocated=sum(row['integers'].values()),
                            difference=population-row['unobserved']-sum(row['integers'].values()),
                            transfer=transfer_ledger,
                            bias=bias(calibrated['observed'],row['integers']))
    category_delta = {key:total-sum(layer['integers'][key] for layer in allocation['layers'].values())
                      for key,total in allocation['totals'].items()}
    transfer_type_delta = {
        key:allocation['transfer_totals'][key]
        - sum(layer['transfer']['integers'][key] for layer in allocation['layers'].values())
        for key in TRANSFER_TYPES
    }
    transfer_known = sum(allocation['transfer_totals'][key] for key in ('transfer_bus','transfer_rail'))
    transfer_untyped = allocation['transfer_totals']['transfer']
    transfer_total_delta = transfer_known + transfer_untyped - allocation['totals']['transfer']
    transfer_observed = sum((Counter(layer['transfer']['observed']) for layer in strata.values()), Counter())
    estimated_delta = allocation['estimated']-sum(allocation['totals'].values())
    unknown_delta = allocation['unknown']-sum(row['unknown'] for row in strata.values())
    gap = frame_total-allocation['estimated']-allocation['unknown']
    transfer_balanced = (transfer_total_delta == 0
                         and not any(transfer_type_delta.values())
                         and all(row['transfer']['integer_delta'] == 0
                                 and row['transfer']['quota_delta'] == '0' for row in strata.values()))
    return dict(population=frame_total, estimated=allocation['estimated'], unknown=allocation['unknown'],
                population_delta=gap, return_delta=line_delta, strata=strata, category_delta=category_delta,
                transfer_types=dict(integers=dict(allocation['transfer_totals']),
                                    observed={key:transfer_observed[key] for key in TRANSFER_TYPES},
                                    type_delta=transfer_type_delta, total_delta=transfer_total_delta,
                                    known=transfer_known, untyped=transfer_untyped,
                                    balanced=transfer_balanced),
                estimated_delta=estimated_delta, unknown_delta=unknown_delta,
                bias=bias(all_observed,allocation['totals']),
                balanced=gap==line_delta==estimated_delta==unknown_delta==0 and not any(category_delta.values())
                and all(row['difference']==0 for row in strata.values()) and transfer_balanced)
