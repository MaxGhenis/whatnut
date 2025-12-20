"""Primary sources and evidence for nut health claims.

Every claim in the analysis must trace back to a source defined here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EffectSize:
    """Quantified effect from a study."""

    metric: str  # "relative_risk", "hazard_ratio", "odds_ratio", "mean_difference"
    point_estimate: float
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    ci_level: float = 0.95  # Default 95% CI


@dataclass
class Source:
    """A primary source for evidence."""

    id: str
    citation: str
    url: str
    study_type: str  # "meta_analysis", "cohort", "rct", "database"
    key_finding: str
    doi: Optional[str] = None
    database: Optional[str] = None  # For non-DOI sources like USDA
    effect_size: Optional[EffectSize] = None
    sample_size: Optional[int] = None
    population: Optional[str] = None


# Primary sources - every claim must trace here
SOURCES: list[Source] = [
    Source(
        id="aune2016",
        citation="Aune D, Keum N, Giovannucci E, et al. Nut consumption and risk of cardiovascular disease, total cancer, all-cause and cause-specific mortality: a systematic review and dose-response meta-analysis of prospective studies. BMC Medicine. 2016;14:207.",
        url="https://bmcmedicine.biomedcentral.com/articles/10.1186/s12916-016-0730-3",
        doi="10.1186/s12916-016-0730-3",
        study_type="meta_analysis",
        key_finding="28g/day nut consumption associated with 22% reduced all-cause mortality",
        effect_size=EffectSize(
            metric="relative_risk",
            point_estimate=0.78,
            ci_lower=0.72,
            ci_upper=0.84,
        ),
        sample_size=819448,
        population="General population from prospective cohort studies",
    ),
    Source(
        id="bao2013",
        citation="Bao Y, Han J, Hu FB, et al. Association of nut consumption with total and cause-specific mortality. N Engl J Med. 2013;369(21):2001-2011.",
        url="https://www.nejm.org/doi/full/10.1056/NEJMoa1307352",
        doi="10.1056/NEJMoa1307352",
        study_type="cohort",
        key_finding="7+ servings/week associated with 20% reduced mortality vs never",
        effect_size=EffectSize(
            metric="hazard_ratio",
            point_estimate=0.80,
            ci_lower=0.73,
            ci_upper=0.86,
        ),
        sample_size=118962,
        population="NHS and HPFS cohorts",
    ),
    Source(
        id="grosso2015",
        citation="Grosso G, Yang J, Marventano S, et al. Nut consumption on all-cause, cardiovascular, and cancer mortality risk: a systematic review and meta-analysis of epidemiologic studies. Am J Clin Nutr. 2015;101(4):783-793.",
        url="https://pubmed.ncbi.nlm.nih.gov/25833976/",
        doi="10.3945/ajcn.114.099515",
        study_type="meta_analysis",
        key_finding="Highest vs lowest nut intake: 19% reduced all-cause mortality",
        effect_size=EffectSize(
            metric="relative_risk",
            point_estimate=0.81,
            ci_lower=0.77,
            ci_upper=0.85,
        ),
        sample_size=354933,
        population="General population from epidemiologic studies",
    ),
    Source(
        id="delgobbo2015",
        citation="Del Gobbo LC, Falk MC, Feldman R, et al. Effects of tree nuts on blood lipids, apolipoproteins, and blood pressure: systematic review, meta-analysis, and dose-response of 61 controlled intervention trials. Am J Clin Nutr. 2015;102(6):1347-1356.",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC4658458/",
        doi="10.3945/ajcn.115.110965",
        study_type="meta_analysis",
        key_finding="Pistachios ranked #1 for LDL and triglyceride reduction among tree nuts",
        effect_size=EffectSize(
            metric="mean_difference",
            point_estimate=-4.8,  # LDL reduction in mg/dL for tree nuts
            ci_lower=-6.3,
            ci_upper=-3.3,
        ),
        sample_size=2582,  # Total participants across 61 trials
        population="Adults in controlled intervention trials",
    ),
    Source(
        id="guasch2017",
        citation="Guasch-Ferré M, Liu X, Malik VS, et al. Nut Consumption and Risk of Cardiovascular Disease. J Am Coll Cardiol. 2017;70(20):2519-2532.",
        url="https://www.jacc.org/doi/10.1016/j.jacc.2017.09.035",
        doi="10.1016/j.jacc.2017.09.035",
        study_type="cohort",
        key_finding="Walnut consumption specifically associated with lower CVD risk",
        effect_size=EffectSize(
            metric="hazard_ratio",
            point_estimate=0.79,
            ci_lower=0.70,
            ci_upper=0.88,
        ),
        sample_size=210836,
        population="NHS, NHS II, and HPFS cohorts",
    ),
    Source(
        id="predimed_walnuts",
        citation="Ros E, et al. PREDIMED Study. Effects of a Mediterranean Diet Supplemented with Nuts on Cardiovascular Risk Factors. Arch Intern Med. 2008.",
        url="https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/414155",
        doi="10.1001/archinte.168.22.2449",
        study_type="rct",
        key_finding="Mediterranean diet + walnuts reduced CVD events vs control",
        sample_size=772,
        population="High CVD risk adults in Spain",
    ),
    Source(
        id="waha2021",
        citation="Rajaram S, et al. Walnuts and Healthy Aging (WAHA) Study. Effects of Daily Walnut Consumption on Cognition and Microbiome. Am J Clin Nutr. 2021.",
        url="https://academic.oup.com/ajcn/article/114/1/75/6178918",
        doi="10.1093/ajcn/nqab051",
        study_type="rct",
        key_finding="2-year walnut supplementation improved lipid profiles in older adults",
        sample_size=708,
        population="Healthy older adults (63-79 years)",
    ),
    Source(
        id="usda_fdc",
        citation="U.S. Department of Agriculture, Agricultural Research Service. FoodData Central.",
        url="https://fdc.nal.usda.gov/",
        database="USDA FoodData Central",
        study_type="database",
        key_finding="Standardized nutrient composition data for all nut types",
    ),
    Source(
        id="fda_macadamia",
        citation="FDA. Qualified Health Claims: Letter of Enforcement Discretion - Nuts and Coronary Heart Disease (Docket No 02P-0505). 2003.",
        url="https://www.fda.gov/food/food-labeling-nutrition/qualified-health-claims-letters-enforcement-discretion",
        study_type="regulatory",
        key_finding="FDA permits qualified health claim for macadamia nuts and CHD risk",
        database="FDA",
    ),
    Source(
        id="mac_rct_2023",
        citation="Neale EP, et al. Macadamia nut effects on cardiometabolic risk factors: a randomised trial. J Nutr Sci. 2023;12:e51.",
        url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10173088/",
        doi="10.1017/jns.2023.37",
        study_type="rct",
        key_finding="8-week macadamia consumption (15% energy): non-significant LDL reduction of 2.1%",
        effect_size=EffectSize(
            metric="mean_difference",
            point_estimate=-4.3,  # mg/dL LDL reduction
            ci_lower=-14.8,
            ci_upper=6.1,
        ),
        sample_size=35,
        population="Adults with abdominal obesity",
    ),
    Source(
        id="griel2008",
        citation="Griel AE, et al. A macadamia nut-rich diet reduces total and LDL-cholesterol in mildly hypercholesterolemic men and women. J Nutr. 2008;138(4):761-767.",
        url="https://pubmed.ncbi.nlm.nih.gov/18356332/",
        doi="10.1093/jn/138.4.761",
        study_type="rct",
        key_finding="Macadamia-rich diet reduced LDL-C by 5.3% vs control",
        sample_size=25,
        population="Mildly hypercholesterolemic adults",
    ),
    Source(
        id="palmitoleic_review",
        citation="Souza CO, et al. Palmitoleic acid in health and disease. In: Advances in Food and Nutrition Research. 2022;100:67-101.",
        url="https://www.sciencedirect.com/science/article/abs/pii/B9780128239148000070",
        doi="10.1016/bs.afnr.2022.04.002",
        study_type="review",
        key_finding="Omega-7 shows promise in animal models but human RCT evidence remains limited",
    ),
]


def get_source(source_id: str) -> Optional[Source]:
    """Get a source by ID."""
    for source in SOURCES:
        if source.id == source_id:
            return source
    return None


def validate_sources() -> list[str]:
    """Validate all sources meet quality requirements. Returns list of errors."""
    errors = []

    for source in SOURCES:
        # Must have URL
        if not source.url or not source.url.startswith("http"):
            errors.append(f"{source.id}: Invalid or missing URL")

        # Must have DOI or database
        if source.doi is None and source.database is None:
            errors.append(f"{source.id}: Must have DOI or database reference")

        # Meta-analyses should have effect sizes
        if source.study_type == "meta_analysis" and source.effect_size is None:
            errors.append(f"{source.id}: Meta-analysis should have effect_size")

    return errors
