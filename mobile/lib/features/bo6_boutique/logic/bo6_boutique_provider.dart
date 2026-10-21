// Owner: BO6 — Riverpod state of the pro space (M14)
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo6_boutique_repository.dart';

final boutiqueRepositoryProvider =
    Provider<BoutiqueRepository>((ref) => BoutiqueRepository());

/// Boutique accounts and stylists (hand-off and clients tabs).
final boutiquesProvider = FutureProvider<List<Pro>>(
    (ref) => ref.read(boutiqueRepositoryProvider).pros(type: 'boutique'));
final stylistsProvider = FutureProvider<List<Pro>>(
    (ref) => ref.read(boutiqueRepositoryProvider).pros(type: 'stylist'));

/// Dashboard of one shop of the catalogue (null = whole market) over [days].
typedef DashboardKey = ({String? shop, int days});
final dashboardProvider = FutureProvider.family<Dashboard, DashboardKey>(
    (ref, key) => ref
        .read(boutiqueRepositoryProvider)
        .dashboard(shop: key.shop, days: key.days));

/// Hand-offs queued for / accepted by a stylist.
final handoffQueueProvider = FutureProvider.family<List<Handoff>, String>(
    (ref, proId) => ref.read(boutiqueRepositoryProvider).queue(proId));

/// Clients of a pro (every link status).
final clientLinksProvider = FutureProvider.family<List<ClientLink>, String>(
    (ref, proId) => ref.read(boutiqueRepositoryProvider).links(proId));

typedef BriefKey = ({String proId, String clientId});
final clientBriefProvider = FutureProvider.family<ClientBrief, BriefKey>(
    (ref, key) =>
        ref.read(boutiqueRepositoryProvider).brief(key.proId, key.clientId));

/// One hand-off (help page).
final handoffProvider = FutureProvider.family<Handoff, String>(
    (ref, id) => ref.read(boutiqueRepositoryProvider).handoff(id));

/// The client's wardrobe and the looks already sent, for one pro.
final wardrobeProvider = FutureProvider.family<List<WardrobePiece>, BriefKey>(
    (ref, key) =>
        ref.read(boutiqueRepositoryProvider).wardrobe(key.proId, key.clientId));
final looksProvider = FutureProvider.family<List<Look>, BriefKey>((ref, key) =>
    ref.read(boutiqueRepositoryProvider).looks(key.proId, key.clientId));

/// Private conversation, read as the stylist or as the client ([reader] = pro_id or client_id).
typedef ChatKey = ({String proId, String clientId, String reader});
final conversationProvider = FutureProvider.family<Conversation, ChatKey>(
    (ref, key) => ref
        .read(boutiqueRepositoryProvider)
        .conversation(key.proId, key.clientId, key.reader));
