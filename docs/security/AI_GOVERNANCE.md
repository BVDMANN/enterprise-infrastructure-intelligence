# AI_GOVERNANCE.md — Enterprise Infrastructure Intelligence

> Version : spécification V3 §7 module 10. Statut : PHASE 0 — règles
> figées avant toute implémentation d'IA. Aucune fonction IA n'existe
> encore dans le produit.

## 1. Finalité

L'IA aide les équipes informatiques à comprendre leurs infrastructures :
résumé d'état, analyse d'incident, explication d'alerte, analyse de
tendances, détection d'anomalies, recommandations, causes possibles,
plans d'action, aide à la documentation, recherche en langage naturel
dans les données autorisées.

Capacités spécialisées envisagées : Infrastructure Analyst, Incident
Analyst, Cost Analyst, Optimization Advisor, Security Analyst,
Automation Planner. **Pas d'agents autonomes indépendants obligatoires** :
préférer une architecture orchestrée, contrôlée et auditable.

## 2. Règles impératives de sécurité IA

L'IA :

- ne possède **pas de privilège administrateur implicite** ;
- ne reçoit que les données **nécessaires** à sa mission ;
- ne peut **pas contourner** le moteur de politiques ;
- ne peut **pas exécuter directement** de commandes libres ;
- ne peut **pas modifier** ses propres permissions ;
- ne peut **pas approuver** ses propres actions ;
- ne peut **pas accéder** à une autre organisation ;
- ne peut **pas utiliser** de secrets auxquels elle n'a pas explicitement accès.

## 3. Moteur de politiques (déterministe, obligatoire)

**Toutes les propositions d'action passent par un moteur déterministe
de politiques et d'autorisations.** Le moteur vérifie :

- identité de l'utilisateur, organisation, rôle ;
- ressource et périmètre ;
- permissions, niveau de risque, état de l'environnement ;
- approbation nécessaire, expiration de l'autorisation.

Aucune action n'est exécutée sans validation de ce moteur, et aucune
action sensible sans validation humaine explicite.

## 4. Données non fiables et prompt injection

Les instructions provenant des logs, des machines, des documents ou des
données collectées sont considérées comme des **données non fiables**.
Elles ne doivent **jamais** devenir des instructions système pour l'IA.

Prévoir : protection contre le prompt injection, limitation des outils
disponibles, validation des entrées et sorties, traçabilité des
recommandations, versionnement des modèles et prompts, contrôle des
coûts, limitation du nombre de requêtes, gestion des erreurs des
fournisseurs IA, possibilité de **désactiver** les fonctions IA.

## 5. Données clients et fournisseurs externes

- Par défaut, **ne pas utiliser les données clients pour entraîner des
  modèles**.
- Toute transmission de données vers un fournisseur IA externe doit
  être **documentée, minimisée** et soumise aux choix contractuels et
  de confidentialité applicables.

## 6. Distinctions obligatoires dans toute réponse d'IA

L'IA doit distinguer clairement :

- **Fait observé** — ce qui a été mesuré / constaté.
- **Hypothèse** — ce qui est supposé, non prouvé.
- **Cause probable** — avec le degré de confiance.
- **Recommandation** — suggestion, non exécutée.
- **Action proposée** — soumise au moteur de politiques.
- **Action réellement exécutée** — avec preuve (journal, vérification).

Ne jamais présenter une hypothèse comme un fait, ni une économie
potentielle comme une économie réalisée.

## 7. Traçabilité

Chaque interaction IA est enregistrée (`ai_interactions`,
`ai_recommendations`) : utilisateur, organisation, type d'analyse,
version du prompt/modèle, données d'entrée (références), sortie,
état de la recommandation (proposée / acceptée / refusée / exécutée),
résultat du contrôle de politique.

## 8. Parcours E — Analyse par IA (référence)

1. L'utilisateur pose une question.
2. Le backend vérifie ses permissions.
3. Les données autorisées sont récupérées et minimisées.
4. L'IA analyse les données.
5. La réponse distingue faits et hypothèses.
6. Les recommandations sont présentées.
7. Toute action potentielle passe par le moteur de politiques.
8. L'utilisateur accepte ou refuse une proposition.
