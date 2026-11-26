/**
 * Explicitly simulated content for the first navigable EII demonstration.
 * Replace each collection with its API query as the corresponding backend
 * endpoint becomes available. Never present these records as customer data.
 */

export const demoNotice =
  "Données de démonstration — valeurs fictives, aucune infrastructure client connectée.";

export const demoOrganizations = [
  {
    name: "Atelier Nord",
    slug: "atelier-nord",
    members: 8,
    assets: 14,
    status: "Actif",
    updated: "Aujourd'hui, 09:42",
  },
  {
    name: "Groupe Horizon",
    slug: "groupe-horizon",
    members: 5,
    assets: 9,
    status: "Actif",
    updated: "Hier, 17:18",
  },
  {
    name: "Nova Services",
    slug: "nova-services",
    members: 3,
    assets: 6,
    status: "À configurer",
    updated: "Hier, 11:06",
  },
] as const;

export const demoUsers = [
  {
    name: "Camille Bernard",
    email: "camille.bernard@example.test",
    organization: "Atelier Nord",
    role: "Administrateur",
    status: "Actif",
  },
  {
    name: "Yanis Moreau",
    email: "yanis.moreau@example.test",
    organization: "Atelier Nord",
    role: "Opérateur",
    status: "Actif",
  },
  {
    name: "Lina Robert",
    email: "lina.robert@example.test",
    organization: "Groupe Horizon",
    role: "Administrateur",
    status: "Actif",
  },
  {
    name: "Alexandre Petit",
    email: "alexandre.petit@example.test",
    organization: "Groupe Horizon",
    role: "Lecteur",
    status: "Invitation",
  },
  {
    name: "Maya Diallo",
    email: "maya.diallo@example.test",
    organization: "Nova Services",
    role: "Opérateur",
    status: "Actif",
  },
] as const;

export const demoAssets = [
  {
    name: "pve-lab-01",
    kind: "Nœud Proxmox",
    environment: "Lab",
    location: "Paris",
    status: "Opérationnel",
    cpu: 32,
    memory: 58,
    lastSeen: "Il y a 2 min",
  },
  {
    name: "srv-api-01",
    kind: "Serveur Debian",
    environment: "Production simulée",
    location: "Paris",
    status: "À surveiller",
    cpu: 82,
    memory: 74,
    lastSeen: "Il y a 5 min",
  },
  {
    name: "vm-db-01",
    kind: "Machine virtuelle",
    environment: "Production simulée",
    location: "Lyon",
    status: "Opérationnel",
    cpu: 41,
    memory: 67,
    lastSeen: "Il y a 3 min",
  },
  {
    name: "edge-gw-01",
    kind: "Passerelle Linux",
    environment: "Lab",
    location: "Lille",
    status: "Hors ligne",
    cpu: 0,
    memory: 0,
    lastSeen: "Il y a 28 min",
  },
] as const;

export const demoEvents = [
  {
    time: "10:42:18",
    date: "Aujourd'hui",
    title: "Seuil CPU dépassé",
    detail: "srv-api-01 · Utilisation CPU à 82 %",
    level: "Avertissement",
    actor: "Supervision simulée",
  },
  {
    time: "10:31:04",
    date: "Aujourd'hui",
    title: "Synchronisation terminée",
    detail: "pve-lab-01 · 6 ressources détectées",
    level: "Information",
    actor: "Connecteur de démonstration",
  },
  {
    time: "09:58:42",
    date: "Aujourd'hui",
    title: "Utilisateur invité",
    detail: "alexandre.petit@example.test · Groupe Horizon",
    level: "Information",
    actor: "Console de démonstration",
  },
  {
    time: "09:14:09",
    date: "Aujourd'hui",
    title: "Connecteur indisponible",
    detail: "edge-gw-01 · Dernier signal reçu il y a 28 min",
    level: "Critique",
    actor: "Supervision simulée",
  },
] as const;
