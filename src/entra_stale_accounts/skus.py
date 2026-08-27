"""Mapping license SKU GUIDs to readable names.

Graph reports a user's licenses as bare SKU GUIDs. The authoritative mapping
for a tenant is its /subscribedSkus endpoint, but reading it requires the
Organization.Read.All permission — so this module also carries a built-in
table of common SKUs to fall back on, and falls back further to the raw GUID
for anything unknown. Names are Microsoft's SKU part numbers (e.g. "SPB" is
Microsoft 365 Business Premium), matching what /subscribedSkus returns.
"""

from __future__ import annotations

from typing import Mapping, Optional

#: Common license SKUs, from Microsoft's licensing service-plan reference.
BUILTIN_SKU_NAMES: dict[str, str] = {
    "3b555118-da6a-4418-894f-7df1e2096870": "O365_BUSINESS_ESSENTIALS",
    "f245ecc8-75af-4f8e-b61f-27d8114de5f3": "O365_BUSINESS_PREMIUM",
    "cbdc14ab-d96c-4c30-b9f4-6ada7cdc1d46": "SPB",
    "05e9a617-0261-4cee-bb44-138d3ef5d965": "SPE_E3",
    "06ebc4ee-1bb5-47dd-8120-11324bc54e06": "SPE_E5",
    "66b55226-6b4f-492c-910c-a3b7a3c9d993": "SPE_F1",
    "18181a46-0d4e-45cd-891e-60aabd171b4e": "STANDARDPACK",
    "6fd2c87f-b296-42f0-b197-1e91e994b900": "ENTERPRISEPACK",
    "c7df2760-2c81-4ef7-b578-5b5392b571df": "ENTERPRISEPREMIUM",
    "4b9405b0-7788-4568-add1-99614e613b69": "EXCHANGESTANDARD",
    "19ec0d23-8335-4cbd-94ac-6050e30712fa": "EXCHANGEENTERPRISE",
    "078d2b04-f1bd-4111-bbd4-b4b1b354cef4": "AAD_PREMIUM",
    "84a661c4-e949-4bd2-a560-ed7766fcaf2b": "AAD_PREMIUM_P2",
    "efccb6f7-5641-4e0e-bd10-b4976e1bf68e": "EMS",
    "b05e124f-c7cc-45a0-a6aa-8cf78c946968": "EMSPREMIUM",
    "a403ebcc-fae0-4ca2-8c8c-7a907fd6c235": "POWER_BI_STANDARD",
    "f8a1db68-be16-40ed-86d5-cb42ce701560": "POWER_BI_PRO",
    "f30db892-07e9-47e9-837c-80727f46fd3d": "FLOW_FREE",
    "c5928f49-12ba-48f7-ada3-0d743a3601d5": "VISIOCLIENT",
    "53818b1b-4a27-454b-8896-0dba576410e6": "PROJECTPROFESSIONAL",
}


def resolve_sku_name(sku_id: str, tenant_names: Optional[Mapping[str, str]] = None) -> str:
    """Best name for a SKU GUID: tenant mapping, then built-ins, then the GUID."""
    key = sku_id.lower()
    if tenant_names and key in tenant_names:
        return tenant_names[key]
    return BUILTIN_SKU_NAMES.get(key, sku_id)
