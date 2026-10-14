// Owner: BO6 (@bo6-owner) — "Où trouver… ?" : search Tunisian shops through M7 (Local catalogue).
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/bo6_local_market_repository.dart';
import '../logic/bo6_local_market_provider.dart';

const _cities = [
  'Tunis',
  'Ariana',
  'La Marsa',
  'Bizerte',
  'Nabeul',
  'Sousse',
  'Sfax',
  'Béja',
  'Le Kef'
];
const _examples = [
  'baskets blanches à Tunis pour 80 TND',
  'robe noire élégante moins de 150 dt',
  'jebba brodée',
  'sac en cuir camel',
  'chemise en lin blanche à la Marsa',
];
const _subcategoryFr = {
  'sneakers': 'Baskets',
  'shoes': 'Chaussures',
  'sandals': 'Sandales',
  'boots': 'Bottes',
  'heels': 'Escarpins',
  'bag': 'Sacs',
  'accessory': 'Accessoires',
  'hijab': 'Hijabs',
  'dress': 'Robes',
  'jumpsuit': 'Combinaisons',
  'set': 'Ensembles',
  'swimwear': 'Maillots',
  'skirt': 'Jupes',
  'shorts': 'Shorts',
  'jeans': 'Jeans',
  'trousers': 'Pantalons',
  'coat': 'Manteaux',
  'jacket': 'Vestes',
  'sweater': 'Pulls',
  'tshirt': 'T-shirts',
  'shirt': 'Chemises',
  'lingerie': 'Lingerie',
  'traditional': 'Tenues traditionnelles',
  'belt': 'Ceintures',
  'jewelry': 'Bijoux',
  'hat': 'Chapeaux',
  'socks': 'Chaussettes',
  'scarf': 'Foulards',
  'sunglasses': 'Lunettes',
  'wallet': 'Portefeuilles',
  'watch': 'Montres',
  'hair': 'Accessoires cheveux',
  'suit': 'Costumes',
  'necklace': 'Colliers',
  'bracelet': 'Bracelets',
  'ring': 'Bagues',
  'earrings': "Boucles d'oreilles",
};
const _colorFr = {
  'black': 'noir',
  'white': 'blanc',
  'grey': 'gris',
  'beige': 'beige',
  'camel': 'camel',
  'brown': 'marron',
  'blue': 'bleu',
  'navy': 'bleu marine',
  'light_blue': 'bleu ciel',
  'red': 'rouge',
  'burgundy': 'bordeaux',
  'pink': 'rose',
  'purple': 'violet',
  'green': 'vert',
  'khaki': 'kaki',
  'yellow': 'jaune',
  'orange': 'orange',
  'gold': 'doré',
  'multicolor': 'multicolore',
};

/// "Tunis; Sousse; Sfax" -> "Tunis +2" (the API already keeps only the matching city under a city filter).
String shortArea(String area) {
  final cities = area.split('; ');
  return cities.length > 1 ? '${cities.first} +${cities.length - 1}' : area;
}

/// 69.3 -> "69,3 TND"
String formatTnd(double value) {
  var text = value.toStringAsFixed(3);
  text = text.replaceFirst(RegExp(r'\.?0+$'), '');
  return '${text.replaceAll('.', ',')} TND';
}

class LocalMarketScreen extends ConsumerStatefulWidget {
  const LocalMarketScreen({super.key});

  @override
  ConsumerState<LocalMarketScreen> createState() => _LocalMarketScreenState();
}

class _LocalMarketScreenState extends ConsumerState<LocalMarketScreen> {
  final _query = TextEditingController();
  final _budget = TextEditingController();
  String? _city;

  @override
  void dispose() {
    _query.dispose();
    _budget.dispose();
    super.dispose();
  }

  void _search([String? text]) {
    if (text != null) _query.text = text;
    final query = _query.text.trim();
    if (query.isEmpty) return;
    FocusScope.of(context).unfocus();
    ref.read(localSearchProvider.notifier).search(
          query: query,
          city: _city,
          maxPriceTnd: double.tryParse(_budget.text.replaceAll(',', '.')),
        );
  }

  @override
  Widget build(BuildContext context) {
    final search = ref.watch(localSearchProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Boutiques locales'),
        actions: [
          IconButton(
            tooltip: 'Boutiques du catalogue',
            icon: const Icon(Icons.storefront_outlined),
            onPressed: () => showModalBottomSheet<void>(
              context: context,
              showDragHandle: true,
              builder: (_) => const _ShopsSheet(),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          _SearchBar(
            query: _query,
            budget: _budget,
            city: _city,
            onCity: (c) => setState(() => _city = c),
            onSearch: _search,
          ),
          Expanded(
            child: search.when(
              loading: () => const _Loading(),
              error: (e, _) =>
                  _Message(icon: Icons.cloud_off, text: describeError(e)),
              data: (result) => result == null
                  ? _Examples(onTap: _search)
                  : _Results(result: result),
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar({
    required this.query,
    required this.budget,
    required this.city,
    required this.onCity,
    required this.onSearch,
  });

  final TextEditingController query;
  final TextEditingController budget;
  final String? city;
  final ValueChanged<String?> onCity;
  final void Function([String?]) onSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: Column(
        children: [
          TextField(
            key: const Key('bo6-query'),
            controller: query,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => onSearch(),
            decoration: InputDecoration(
              hintText: 'Ex. baskets blanches à Tunis pour 80 TND',
              prefixIcon: const Icon(Icons.search),
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                  icon: const Icon(Icons.arrow_forward),
                  onPressed: () => onSearch()),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String?>(
                  initialValue: city,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Ville',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Toutes')),
                    for (final c in _cities)
                      DropdownMenuItem(value: c, child: Text(c)),
                  ],
                  onChanged: onCity,
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 130,
                child: TextField(
                  controller: budget,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  onSubmitted: (_) => onSearch(),
                  decoration: const InputDecoration(
                    labelText: 'Budget max',
                    suffixText: 'TND',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Examples extends StatelessWidget {
  const _Examples({required this.onTap});

  final void Function([String?]) onTap;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Trouve une pièce dans les boutiques tunisiennes',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 4),
        Text(
          'Décris ce que tu cherches, ta ville et ton budget en TND. Exemples :',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final e in _examples)
              ActionChip(label: Text(e), onPressed: () => onTap(e))
          ],
        ),
      ],
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 12),
          Text('Recherche dans les boutiques…'),
        ],
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(text, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _Results extends ConsumerWidget {
  const _Results({required this.result});

  final LocalSearchResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final parsed = result.parsed;
    final understood = <String>[
      if (parsed?.subcategory != null)
        _subcategoryFr[parsed!.subcategory] ?? parsed.subcategory!,
      if (parsed?.subcategory == null && parsed?.category != null)
        parsed!.category!,
      if (parsed?.color != null) _colorFr[parsed!.color] ?? parsed.color!,
      if (parsed?.minPriceTnd != null) '≥ ${formatTnd(parsed!.minPriceTnd!)}',
      if (parsed?.maxPriceTnd != null) '≤ ${formatTnd(parsed!.maxPriceTnd!)}',
      if (parsed?.city != null) parsed!.city!,
    ];
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          sliver: SliverList.list(
            children: [
              Text(
                '${result.totalMatches} article${result.totalMatches > 1 ? 's' : ''} trouvé'
                '${result.totalMatches > 1 ? 's' : ''}'
                '${result.totalMatches > result.results.length ? ' · ${result.results.length} meilleurs' : ''}',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              if (parsed?.corrected != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Recherche corrigée : « ${parsed!.corrected} »',
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(fontStyle: FontStyle.italic),
                ),
              ],
              if (understood.isNotEmpty) ...[
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Text('Compris : '),
                    for (final u in understood)
                      Chip(
                          label: Text(u), visualDensity: VisualDensity.compact),
                  ],
                ),
              ],
              if (result.note != null) ...[
                const SizedBox(height: 8),
                Card(
                  color: Theme.of(context).colorScheme.secondaryContainer,
                  child: ListTile(
                      leading: const Icon(Icons.info_outline),
                      title: Text(result.note!)),
                ),
              ],
            ],
          ),
        ),
        if (result.results.isEmpty)
          const SliverFillRemaining(
            hasScrollBody: false,
            child: _Message(
                icon: Icons.search_off,
                text: 'Aucun article. Élargis le budget ou la ville.'),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
            sliver: SliverGrid.builder(
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 240,
                mainAxisSpacing: 8,
                crossAxisSpacing: 8,
                childAspectRatio: 0.58,
              ),
              itemCount: result.results.length,
              itemBuilder: (_, i) => _ProductCard(product: result.results[i]),
            ),
          ),
      ],
    );
  }
}

class _ProductCard extends ConsumerWidget {
  const _ProductCard({required this.product});

  final LocalProduct product;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.watch(localMarketRepositoryProvider);
    final theme = Theme.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => showModalBottomSheet<void>(
          context: context,
          isScrollControlled: true,
          showDragHandle: true,
          builder: (_) =>
              _ProductSheet(product: product, photoUrl: repo.photoUrl(product)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: _Photo(url: repo.photoUrl(product))),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(product.item,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium),
                  const SizedBox(height: 2),
                  Text(
                    [
                      product.shop,
                      if (product.area != null) shortArea(product.area!)
                    ].join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          product.priceTnd == null
                              ? 'Prix ?'
                              : formatTnd(product.priceTnd!),
                          style: theme.textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ),
                      Text('${(product.match * 100).round()} %',
                          style: theme.textTheme.labelSmall),
                    ],
                  ),
                  const SizedBox(height: 4),
                  LinearProgressIndicator(
                      value: product.match,
                      minHeight: 4,
                      borderRadius: BorderRadius.circular(2)),
                  if (!product.available) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Rupture de stock',
                      style: theme.textTheme.labelSmall
                          ?.copyWith(color: theme.colorScheme.error),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Photo extends StatelessWidget {
  const _Photo({required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Image.network(
        url,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) =>
            const Center(child: Icon(Icons.image_not_supported_outlined)),
        loadingBuilder: (_, child, progress) => progress == null
            ? child
            : const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      ),
    );
  }
}

class _ProductSheet extends StatelessWidget {
  const _ProductSheet({required this.product, required this.photoUrl});

  final LocalProduct product;
  final String photoUrl;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(aspectRatio: 1, child: _Photo(url: photoUrl)),
          ),
          const SizedBox(height: 12),
          Text(product.item, style: theme.textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(
            [product.shop, if (product.area != null) product.area!].join(' · '),
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              Chip(
                  label: Text(product.priceTnd == null
                      ? 'Prix ?'
                      : formatTnd(product.priceTnd!))),
              Chip(
                  label: Text(
                      'Correspondance ${(product.match * 100).round()} %')),
              if (product.isLocalBrand)
                const Chip(
                    avatar: Icon(Icons.flag_outlined, size: 18),
                    label: Text('Marque tunisienne')),
              if (!product.available)
                const Chip(label: Text('Rupture de stock')),
            ],
          ),
          if (product.size != null) ...[
            const SizedBox(height: 8),
            Text('Tailles disponibles : ${product.size}'),
          ],
          const SizedBox(height: 12),
          Text('Pourquoi cette pièce', style: theme.textTheme.titleSmall),
          for (final r in product.reasons)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.check_circle_outline, size: 20),
              title: Text(r),
            ),
          const SizedBox(height: 8),
          Text('Fiche produit', style: theme.textTheme.titleSmall),
          SelectableText(product.productUrl, style: theme.textTheme.bodySmall),
          const SizedBox(height: 8),
          FilledButton.tonalIcon(
            icon: const Icon(Icons.link),
            label: const Text('Copier le lien de la boutique'),
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: product.productUrl));
              if (context.mounted) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(const SnackBar(content: Text('Lien copié')));
              }
            },
          ),
        ],
      ),
    );
  }
}

class _ShopsSheet extends ConsumerWidget {
  const _ShopsSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final shops = ref.watch(localShopsProvider);
    return shops.when(
      loading: () => const Padding(
          padding: EdgeInsets.all(32),
          child: Center(child: CircularProgressIndicator())),
      error: (e, _) => _Message(icon: Icons.cloud_off, text: describeError(e)),
      data: (list) => ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text('${list.length} boutiques tunisiennes',
                style: Theme.of(context).textTheme.titleMedium),
          ),
          for (final s in list)
            ListTile(
              leading: const Icon(Icons.storefront_outlined),
              title: Text(s.shop),
              subtitle:
                  Text([s.city ?? 'Ville non précisée', s.shopUrl].join(' · ')),
              trailing: Text('${s.products}'),
            ),
        ],
      ),
    );
  }
}
