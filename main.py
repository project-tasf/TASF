from argparse import ArgumentParser
from collections import Counter
from json import dumps
from random import Random

from Baseline import BASELINES, BaselineCampaign
from tasf.benches import default_registry
from tasf.campaign import Campaign, RoundResult, Settings
from tasf.model import Profile
from tasf.observation import AccumulatorReference
from tasf.seeding import sample_seeds


def accumulator_campaign(
    settings: Settings = Settings(max_cycles=2048), *, method: str = "TASF",
) -> tuple[RoundResult, ...]:
    registry = default_registry()
    profile = Profile()

    def bench_factory():
        return registry.create("accumulator", latency=1)

    if method == "TASF":
        campaign = Campaign(bench_factory, AccumulatorReference, settings=settings, profile=profile)
    elif method in BASELINES:
        campaign = BaselineCampaign(
            BASELINES[method](), bench_factory, AccumulatorReference, settings=settings, profile=profile,
        )
    else:
        raise ValueError(f"Unknown testing method: {method}")
    seeds = sample_seeds(profile, Random(settings.random_seed), count=4)
    campaign.calibrate(seeds)
    return campaign.run()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--method", choices=("TASF", *BASELINES), default="TASF")
    method = parser.parse_args().method
    rounds = accumulator_campaign(method=method)
    print(dumps({
        "rounds": len(rounds),
        "status": dict(Counter(result.status for result in rounds)),
        "new_features": sum(result.new_features for result in rounds),
        "retained_cases": sum(result.added for result in rounds),
    }))
