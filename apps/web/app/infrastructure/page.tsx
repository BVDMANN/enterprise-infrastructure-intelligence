"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Database,
  HardDrive,
  Network,
  Plus,
  RefreshCw,
  Server,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/page-heading";
import {
  ApiError,
  createInfrastructureAsset,
  deleteInfrastructureAsset,
  getOrganizationInfrastructureAssets,
  getOrganizations,
  updateInfrastructureAsset,
  type InfrastructureAsset,
  type InfrastructureAssetInput,
  type InfrastructureAssetStatus,
  type InfrastructureAssetType,
} from "@/lib/api";
import { useCsrfToken } from "@/lib/csrf-token";

const typeLabels: Record<InfrastructureAssetType, string> = {
  server: "Serveur",
  virtual_machine: "Machine virtuelle",
  container: "Conteneur",
  cluster: "Cluster",
  database: "Base de données",
  network: "Réseau",
  storage: "Stockage",
  cloud_resource: "Ressource cloud",
  service: "Service",
  other: "Autre",
};

const statusLabels: Record<InfrastructureAssetStatus, string> = {
  unknown: "Inconnu",
  healthy: "Opérationnel",
  degraded: "Dégradé",
  unhealthy: "En anomalie",
  offline: "Hors ligne",
};

const statusStyles: Record<InfrastructureAssetStatus, string> = {
  unknown: "bg-slate-100 text-slate-600",
  healthy: "bg-emerald-50 text-emerald-700",
  degraded: "bg-amber-50 text-amber-700",
  unhealthy: "bg-rose-50 text-rose-700",
  offline: "bg-slate-200 text-slate-700",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Votre session a expiré. Reconnectez-vous.";
    if (error.status === 403) return "Votre rôle ne permet pas cette opération.";
    if (error.status === 404) return "Organisation ou ressource introuvable.";
    if (error.status === 409) return "Cet identifiant externe existe déjà dans cette organisation.";
    if (error.status === 422) return error.message;
    return error.message;
  }
  return "Une erreur inattendue empêche de communiquer avec l’API.";
}

function formatDate(value: string | null): string {
  if (!value) return "Aucun signal fourni";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date non valide";
  return date.toLocaleString("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function AssetIcon({ type }: { type: InfrastructureAssetType }) {
  if (type === "database") return <Database aria-hidden="true" className="h-5 w-5" />;
  if (type === "network") return <Network aria-hidden="true" className="h-5 w-5" />;
  if (type === "storage") return <HardDrive aria-hidden="true" className="h-5 w-5" />;
  return <Server aria-hidden="true" className="h-5 w-5" />;
}

export default function InfrastructurePage() {
  const queryClient = useQueryClient();
  const csrfToken = useCsrfToken();
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [statusFilter, setStatusFilter] = useState<InfrastructureAssetStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<InfrastructureAssetType | "all">("all");
  const [name, setName] = useState("");
  const [assetType, setAssetType] = useState<InfrastructureAssetType>("server");
  const [externalId, setExternalId] = useState("");
  const [provider, setProvider] = useState("");
  const [region, setRegion] = useState("");

  const organizations = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
    staleTime: 30_000,
  });
  const organizationId =
    selectedOrganizationId || organizations.data?.[0]?.id || "";

  const assets = useQuery({
    queryKey: ["infrastructure-assets", organizationId, statusFilter, typeFilter],
    queryFn: () =>
      getOrganizationInfrastructureAssets(organizationId, {
        status: statusFilter === "all" ? undefined : statusFilter,
        asset_type: typeFilter === "all" ? undefined : typeFilter,
        limit: 100,
      }),
    enabled: Boolean(organizationId),
    retry: false,
    staleTime: 15_000,
  });

  const invalidateAssets = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["infrastructure-assets", organizationId],
    });
  };

  const createMutation = useMutation({
    mutationFn: (payload: InfrastructureAssetInput) => {
      if (!csrfToken) throw new ApiError(401, "A session CSRF token is required.");
      return createInfrastructureAsset(organizationId, payload, csrfToken);
    },
    onSuccess: async () => {
      setName("");
      setExternalId("");
      setProvider("");
      setRegion("");
      await invalidateAssets();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: { assetId: string; status: InfrastructureAssetStatus }) => {
      if (!csrfToken) throw new ApiError(401, "A session CSRF token is required.");
      return updateInfrastructureAsset(
        organizationId,
        input.assetId,
        { status: input.status },
        csrfToken,
      );
    },
    onSuccess: invalidateAssets,
  });

  const deleteMutation = useMutation({
    mutationFn: (assetId: string) => {
      if (!csrfToken) throw new ApiError(401, "A session CSRF token is required.");
      return deleteInfrastructureAsset(organizationId, assetId, csrfToken);
    },
    onSuccess: invalidateAssets,
  });

  function submitAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate({
      name: name.trim(),
      asset_type: assetType,
      external_id: externalId.trim() || null,
      provider: provider.trim() || null,
      region: region.trim() || null,
      status: "unknown",
      attributes: {},
    });
  }

  const assetsList = assets.data ?? [];
  const healthyCount = assetsList.filter((asset) => asset.status === "healthy").length;
  const attentionCount = assetsList.filter(
    (asset) => asset.status === "degraded" || asset.status === "unhealthy",
  ).length;
  const offlineCount = assetsList.filter((asset) => asset.status === "offline").length;
  const mutationError =
    createMutation.error ?? updateMutation.error ?? deleteMutation.error;

  return (
    <AppShell>
      <PageHeading
        eyebrow="Inventaire connecté"
        title="Infrastructure"
        description="Inventaire des ressources enregistré dans l’API EII pour une organisation autorisée."
      />

      <div className="mb-6 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        <strong>API réelle : inventaire CRUD.</strong> Les métriques CPU/mémoire,
        la collecte automatique, les connecteurs et les alertes ne sont pas encore implémentés.
        Aucun signal temps réel n’est simulé sur cette page.
      </div>

      {organizations.isLoading && (
        <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
          Chargement des organisations accessibles…
        </p>
      )}

      {organizations.isError && (
        <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {errorMessage(organizations.error)}
        </p>
      )}

      {organizations.data && organizations.data.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-900">Aucune organisation accessible</h2>
          <p className="mt-1 text-sm text-slate-500">
            Rejoignez une organisation ou créez-en une avant d’y enregistrer des ressources.
          </p>
        </div>
      )}

      {organizationId && (
        <>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <label className="block min-w-64 text-xs font-medium text-slate-600">
              Organisation
              <select
                value={organizationId}
                onChange={(event) => setSelectedOrganizationId(event.target.value)}
                className="mt-1.5 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
              >
                {(organizations.data ?? []).map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void assets.refetch()}
              disabled={assets.isFetching}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw aria-hidden="true" className={assets.isFetching ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
              Actualiser
            </button>
          </div>

          <section aria-label="Indicateurs d’inventaire" className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Ressources filtrées</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
                {assets.isLoading ? "—" : assetsList.length}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Opérationnelles</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-700">
                {assets.isLoading ? "—" : healthyCount}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">À surveiller / anomalie</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-700">
                {assets.isLoading ? "—" : attentionCount}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Hors ligne</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-700">
                {assets.isLoading ? "—" : offlineCount}
              </p>
            </div>
          </section>

          <details className="mb-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold text-slate-900">
              <Plus aria-hidden="true" className="h-4 w-4 text-accent" />
              Enregistrer une ressource
            </summary>
            <form onSubmit={submitAsset} className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="text-xs font-medium text-slate-600">
                Nom de la ressource
                <input
                  required
                  maxLength={255}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="srv-api-01"
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                />
              </label>
              <label className="text-xs font-medium text-slate-600">
                Type
                <select
                  value={assetType}
                  onChange={(event) => setAssetType(event.target.value as InfrastructureAssetType)}
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm"
                >
                  {Object.entries(typeLabels).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-medium text-slate-600">
                Identifiant externe (facultatif)
                <input
                  maxLength={255}
                  value={externalId}
                  onChange={(event) => setExternalId(event.target.value)}
                  placeholder="vm-123"
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                />
              </label>
              <label className="text-xs font-medium text-slate-600">
                Fournisseur (facultatif)
                <input
                  maxLength={128}
                  value={provider}
                  onChange={(event) => setProvider(event.target.value)}
                  placeholder="Proxmox, AWS, Azure…"
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                />
              </label>
              <label className="text-xs font-medium text-slate-600">
                Région / emplacement (facultatif)
                <input
                  maxLength={128}
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  placeholder="eu-west-3"
                  className="mt-1.5 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                />
              </label>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={createMutation.isPending || !name.trim() || !csrfToken}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus aria-hidden="true" className="h-4 w-4" />
                  {createMutation.isPending ? "Enregistrement…" : "Enregistrer"}
                </button>
              </div>
              <p className="text-xs text-slate-400 md:col-span-2">
                Les champs secrets et identifiants sensibles ne doivent jamais être placés dans les attributs d’inventaire.
              </p>
            </form>
          </details>

          {mutationError && (
            <p role="alert" className="mb-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
              {errorMessage(mutationError)}
            </p>
          )}

          <div className="mb-4 flex flex-wrap gap-3">
            <label className="text-xs font-medium text-slate-600">
              Type
              <select
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value as InfrastructureAssetType | "all")}
                className="mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">Tous les types</option>
                {Object.entries(typeLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              Statut
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as InfrastructureAssetStatus | "all")}
                className="mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">Tous les statuts</option>
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </div>

          {assets.isLoading && (
            <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
              Chargement de l’inventaire depuis l’API…
            </p>
          )}

          {assets.isError && (
            <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
              {errorMessage(assets.error)}
            </p>
          )}

          {assets.data && assets.data.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
              <Server aria-hidden="true" className="mx-auto h-8 w-8 text-slate-300" />
              <h2 className="mt-3 font-semibold text-slate-900">Aucune ressource enregistrée</h2>
              <p className="mt-1 text-sm text-slate-500">
                Ajoutez un serveur, une base de données ou une autre ressource pour commencer l’inventaire.
              </p>
            </div>
          )}

          <section aria-label="Ressources d’infrastructure" className="grid gap-4 xl:grid-cols-2">
            {assetsList.map((asset: InfrastructureAsset) => (
              <article key={asset.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                      <AssetIcon type={asset.asset_type} />
                    </div>
                    <div className="min-w-0">
                      <h2 className="truncate font-semibold text-slate-900">{asset.name}</h2>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {typeLabels[asset.asset_type]}
                        {asset.provider ? " · " + asset.provider : ""}
                        {asset.region ? " · " + asset.region : ""}
                      </p>
                    </div>
                  </div>
                  <span className={"shrink-0 rounded-full px-2.5 py-1 text-xs font-medium " + statusStyles[asset.status]}>
                    {statusLabels[asset.status]}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                  <div className="text-xs text-slate-500">
                    <p>Identifiant : {asset.external_id || "Non renseigné"}</p>
                    <p className="mt-1">Dernier signal déclaré : {formatDate(asset.last_seen_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="sr-only" htmlFor={"status-" + asset.id}>Modifier le statut de {asset.name}</label>
                    <select
                      id={"status-" + asset.id}
                      value={asset.status}
                      disabled={updateMutation.isPending || !csrfToken}
                      onChange={(event) =>
                        updateMutation.mutate({
                          assetId: asset.id,
                          status: event.target.value as InfrastructureAssetStatus,
                        })
                      }
                      className="max-w-36 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700 disabled:opacity-50"
                    >
                      {Object.entries(statusLabels).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      title={"Supprimer " + asset.name}
                      aria-label={"Supprimer " + asset.name}
                      disabled={deleteMutation.isPending || !csrfToken}
                      onClick={() => {
                        if (window.confirm("Supprimer logiquement la ressource « " + asset.name + " » ?")) {
                          deleteMutation.mutate(asset.id);
                        }
                      }}
                      className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
                    >
                      <Trash2 aria-hidden="true" className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </section>

          <p className="mt-5 flex items-center gap-2 text-xs text-slate-400">
            <Activity aria-hidden="true" className="h-3.5 w-3.5" />
            Les statuts sont ceux enregistrés dans l’inventaire. Ils ne sont pas calculés par un agent de supervision.
          </p>
        </>
      )}
    </AppShell>
  );
}
