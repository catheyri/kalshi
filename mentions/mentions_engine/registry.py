from __future__ import annotations

from typing import Dict, List, Optional

from mentions_engine.acquisition import AcquisitionAdapter, WhiteHouseAcquisition
from mentions_engine.config import AppPaths
from mentions_engine.event_mapping import EventMapper, WhiteHouseEventMapper
from mentions_engine.discovery import DiscoveryAdapter, WhiteHouseDiscovery
from mentions_engine.http import HttpClient
from mentions_engine.prediction import (
    FeatureExtractor,
    HistoricalFrequencyPricingModel,
    HistoricalOutcomeFeatureExtractor,
    OpportunityScorer,
    PricingModel,
    SimpleOpportunityScorer,
)
from mentions_engine.storage import Database
from mentions_engine.transcripts import TranscriptBuilder, WhiteHouseTranscriptBuilder


def discovery_adapters(client: Optional[HttpClient] = None) -> Dict[str, DiscoveryAdapter]:
    whitehouse = WhiteHouseDiscovery(client=client)
    return {
        whitehouse.name: whitehouse,
        "white_house_press_briefing": whitehouse,
    }


def acquisition_adapters(paths: AppPaths, client: Optional[HttpClient] = None) -> Dict[str, AcquisitionAdapter]:
    whitehouse = WhiteHouseAcquisition(paths=paths, client=client)
    return {
        whitehouse.event_type: whitehouse,
    }


def transcript_builders() -> List[TranscriptBuilder]:
    return [WhiteHouseTranscriptBuilder()]


def event_mappers() -> List[EventMapper]:
    return [WhiteHouseEventMapper()]


def feature_extractor(db: Database) -> FeatureExtractor:
    return HistoricalOutcomeFeatureExtractor(db)


def pricing_model() -> PricingModel:
    return HistoricalFrequencyPricingModel()


def opportunity_scorer() -> OpportunityScorer:
    return SimpleOpportunityScorer()
