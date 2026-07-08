from datetime import datetime
from typing import Any, Literal

import oci
from oci.usage_api.models import RequestSummarizedUsagesDetails

Granularity = Literal["DAILY", "MONTHLY"]


class UsageGateway:
    def __init__(self, client: Any, tenant_id: str) -> None:
        self._client = client
        self._tenant_id = tenant_id

    def request_costs(
        self,
        *,
        started: datetime,
        ended: datetime,
        granularity: Granularity,
        group_by: list[str] | None = None,
    ) -> list[Any]:
        details = RequestSummarizedUsagesDetails(
            tenant_id=self._tenant_id,
            time_usage_started=started,
            time_usage_ended=ended,
            granularity=granularity,
            query_type="COST",
            group_by=group_by or [],
        )
        response = self._client.request_summarized_usages(details)
        return list(response.data.items or [])


def build_instance_principal_gateway() -> UsageGateway:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    client = oci.usage_api.UsageapiClient(config={}, signer=signer)
    return UsageGateway(client, tenant_id=signer.tenancy_id)
