from app.config import CHOICES, TRANSFER_TYPES

from .remainders import largest_remainders, split_transfer


def expand(calibrated):
    layers, total, unknown = {}, dict.fromkeys(CHOICES,0), 0
    transfer_totals = dict.fromkeys(TRANSFER_TYPES, 0)
    for name, layer in calibrated['layers'].items():
        unobserved = layer['population'] if layer['status']=='zero_response' else 0
        result = largest_remainders(layer['quotas'],layer['population']-unobserved)
        transfer_result = split_transfer(layer['transfer_quotas'], result['integers']['transfer'])
        layers[name] = {**result,'population':layer['population'],'unobserved':unobserved,'status':layer['status'],
                        'transfer':transfer_result}
        unknown += unobserved
        for key,value in result['integers'].items():
            total[key] += value
        for key,value in transfer_result['integers'].items():
            transfer_totals[key] += value
    return dict(layers=layers, totals=total, unknown=unknown, estimated=sum(total.values()),
                transfer_totals=transfer_totals)
