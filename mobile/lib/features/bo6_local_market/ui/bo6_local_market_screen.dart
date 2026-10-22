// Owner: BO6 (@bo6-owner) — "Where to find…?": search Tunisian shops through M7 (Local catalogue).
// Look: DressMe design (docs/design/, "Local" tab and "Local selection" of the prototype). English UI.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/design/dressme_design.dart';
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
  'white sneakers in Tunis for 80 TND',
  'elegant black dress under 150 dt',
  'embroidered jebba',
  'camel leather bag',
  'white linen shirt in La Marsa',
];
const _subcategoryEn = {
  'sneakers': 'Sneakers',
  'shoes': 'Shoes',
  'sandals': 'Sandals',
  'boots': 'Boots',
  'heels': 'Heels',
  'bag': 'Bags',
  'accessory': 'Accessories',
  'hijab': 'Hijabs',
  'dress': 'Dresses',
  'jumpsuit': 'Jumpsuits',
  'set': 'Sets',
  'swimwear': 'Swimwear',
  'skirt': 'Skirts',
  'shorts': 'Shorts',
  'jeans': 'Jeans',
  'trousers': 'Trousers',
  'coat': 'Coats',
  'jacket': 'Jackets',
  'sweater': 'Sweaters',
  'tshirt': 'T-shirts',
  'shirt': 'Shirts',
  'lingerie': 'Lingerie',
  'traditional': 'Traditional outfits',
  'belt': 'Belts',
  'jewelry': 'Jewellery',
  'hat': 'Hats',
  'socks': 'Socks',
  'scarf': 'Scarves',
  'sunglasses': 'Sunglasses',
  'wallet': 'Wallets',
  'watch': 'Watches',
  'hair': 'Hair accessories',
  'suit': 'Suits',
  'necklace': 'Necklaces',
  'bracelet': 'Bracelets',
  'ring': 'Rings',
  'earrings': 'Earrings',
};
const _colorEn = {
  'navy': 'navy blue',
  'light_blue': 'light blue',
  'multicolor': 'multicolour',
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

  void _pickCity(String? city) {
    setState(() => _city = city);
    if (_query.text.trim().isNotEmpty) _search();
  }

  @override
  Widget build(BuildContext context) {
    final search = ref.watch(localSearchProvider);
    return Theme(
      data: dressMeTheme(),
      child: Builder(
        builder: (context) => Scaffold(
          body: Column(
            children: [
              _Hero(
                query: _query,
                budget: _budget,
                onSearch: _search,
                onShops: () => showModalBottomSheet<void>(
                  context: context,
                  showDragHandle: true,
                  builder: (_) => const _ShopsSheet(),
                ),
              ),
              _CityChips(city: _city, onCity: _pickCity),
              Expanded(
                child: search.when(
                  loading: () => const _Loading(),
                  error: (e, _) => _Message(
                      icon: Icons.cloud_off_outlined, text: describeError(e)),
                  data: (result) => result == null
                      ? _Examples(onTap: _search)
                      : _Results(result: result),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Dark header of the prototype: eyebrow, serif title, search field and budget.
class _Hero extends StatelessWidget {
  const _Hero({
    required this.query,
    required this.budget,
    required this.onSearch,
    required this.onShops,
  });

  final TextEditingController query;
  final TextEditingController budget;
  final void Function([String?]) onSearch;
  final VoidCallback onShops;

  @override
  Widget build(BuildContext context) {
    final onDark = Colors.white.withValues(alpha: 0.55);
    return Container(
      color: DmColors.inkDeep,
      child: Stack(
        children: [
          // Soft gold glow, as in the prototype's headers.
          Positioned(
            right: -70,
            top: -90,
            child: Container(
              width: 260,
              height: 260,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: [
                  const Color(0xFF9C7650).withValues(alpha: 0.35),
                  const Color(0xFF9C7650).withValues(alpha: 0),
                ]),
              ),
            ),
          ),
          SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('TUNISIAN FASHION',
                                style: DmText.eyebrow
                                    .copyWith(color: DmColors.gold)),
                            const SizedBox(height: 4),
                            Text('Local shops',
                                style: DmText.display
                                    .copyWith(color: Colors.white)),
                            const SizedBox(height: 6),
                            Text(
                                'Prices in dinars, local availability and style match.',
                                style: DmText.body.copyWith(color: onDark)),
                          ],
                        ),
                      ),
                      Tooltip(
                        message: 'Pro space (shops and stylists)',
                        child: InkResponse(
                          onTap: () => context.go('/bo6_boutique'),
                          child: Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: Colors.white.withValues(alpha: 0.1),
                              border: Border.all(
                                  color: Colors.white.withValues(alpha: 0.2)),
                            ),
                            child: const Icon(Icons.insights_outlined,
                                color: Colors.white, size: 20),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Tooltip(
                        message: 'Catalogue shops',
                        child: InkResponse(
                          onTap: onShops,
                          child: Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: Colors.white.withValues(alpha: 0.1),
                              border: Border.all(
                                  color: Colors.white.withValues(alpha: 0.2)),
                            ),
                            child: const Icon(Icons.storefront_outlined,
                                color: Colors.white, size: 20),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          key: const Key('bo6-query'),
                          controller: query,
                          textInputAction: TextInputAction.search,
                          onSubmitted: (_) => onSearch(),
                          style: const TextStyle(
                              fontSize: 13, color: DmColors.text),
                          decoration: InputDecoration(
                            hintText:
                                'e.g. white sneakers in Tunis for 80 TND',
                            prefixIcon: const Icon(Icons.search,
                                color: DmColors.bronzeDark),
                            suffixIcon: IconButton(
                              tooltip: 'Search',
                              icon: const Icon(Icons.arrow_forward,
                                  color: DmColors.ink),
                              onPressed: () => onSearch(),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      SizedBox(
                        width: 112,
                        child: TextField(
                          controller: budget,
                          keyboardType: const TextInputType.numberWithOptions(
                              decimal: true),
                          onSubmitted: (_) => onSearch(),
                          style: const TextStyle(
                              fontSize: 13, color: DmColors.text),
                          decoration: const InputDecoration(
                            hintText: 'Budget',
                            suffixText: 'TND',
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// City filter as the prototype's pills: selected = ink, others = white with a border.
class _CityChips extends StatelessWidget {
  const _CityChips({required this.city, required this.onCity});

  final String? city;
  final ValueChanged<String?> onCity;

  @override
  Widget build(BuildContext context) {
    final options = <(String, String?)>[
      ('All', null),
      for (final c in _cities) (c, c),
    ];
    return SizedBox(
      height: 60,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        itemCount: options.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final (label, value) = options[i];
          final selected = value == city;
          return ChoiceChip(
            label: Text(label),
            selected: selected,
            labelStyle: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: selected ? Colors.white : DmColors.mutedDark,
            ),
            side: BorderSide(
                color: selected ? DmColors.ink : DmColors.borderStrong),
            onSelected: (_) => onCity(value),
          );
        },
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
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      children: [
        const DmSectionHeader(
            eyebrow: 'Where to find…?', title: 'What are you looking for?'),
        const SizedBox(height: 6),
        const Text(
          'Describe the piece, your city and your budget in TND: '
          'DressMe searches the Tunisian shops.',
          style: DmText.body,
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final e in _examples)
              ActionChip(
                label: Text(e),
                labelStyle:
                    const TextStyle(fontSize: 11, color: DmColors.mutedDark),
                onPressed: () => onTap(e),
              ),
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
          SizedBox(
            width: 28,
            height: 28,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
          SizedBox(height: 12),
          Text('Searching the shops…', style: DmText.caption),
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
            Icon(icon, size: 40, color: DmColors.muted),
            const SizedBox(height: 12),
            Text(text, textAlign: TextAlign.center, style: DmText.body),
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
        _subcategoryEn[parsed!.subcategory] ?? parsed.subcategory!,
      if (parsed?.subcategory == null && parsed?.category != null)
        parsed!.category!,
      if (parsed?.color != null) _colorEn[parsed!.color] ?? parsed.color!.replaceAll('_', ' '),
      if (parsed?.gender == 'men') 'Men',
      if (parsed?.gender == 'women') 'Women',
      if (parsed?.minPriceTnd != null) '≥ ${formatTnd(parsed!.minPriceTnd!)}',
      if (parsed?.maxPriceTnd != null) '≤ ${formatTnd(parsed!.maxPriceTnd!)}',
      if (parsed?.city != null) parsed!.city!,
    ];
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          sliver: SliverList.list(
            children: [
              const Text('LOCAL SELECTION', style: DmText.eyebrow),
              const SizedBox(height: 2),
              Text(
                '${result.totalMatches} piece${result.totalMatches > 1 ? 's' : ''} found'
                '${result.totalMatches > result.results.length ? ' · ${result.results.length} shown' : ''}',
                style: DmText.title,
              ),
              if (parsed?.translated != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Darija understood: "${parsed!.translated}"',
                  style: DmText.caption.copyWith(fontStyle: FontStyle.italic),
                ),
              ],
              if (parsed?.corrected != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Search corrected: "${parsed!.corrected}"',
                  style: DmText.caption.copyWith(fontStyle: FontStyle.italic),
                ),
              ],
              if (understood.isNotEmpty) ...[
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Text('Understood:', style: DmText.caption),
                    for (final u in understood) DmPill(u),
                  ],
                ),
              ],
              if (result.note != null) ...[
                const SizedBox(height: 12),
                _NoteCard(text: result.note!),
              ],
            ],
          ),
        ),
        if (result.results.isEmpty)
          const SliverFillRemaining(
            hasScrollBody: false,
            child: _Message(
                icon: Icons.search_off,
                text: 'No piece. Widen the budget or the city.'),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            sliver: SliverGrid.builder(
              gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                maxCrossAxisExtent: 230,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.56,
              ),
              itemCount: result.results.length,
              itemBuilder: (_, i) => _ProductCard(
                  product: result.results[i],
                  searchId: result.searchId,
                  rank: i + 1),
            ),
          ),
        if (result.hasMore)
          SliverToBoxAdapter(
            child: _MoreButtons(
                remaining: result.totalMatches - result.results.length),
          ),
      ],
    );
  }
}

/// "Show more" (next page) and "Show all" (every remaining result) under the grid.
class _MoreButtons extends ConsumerStatefulWidget {
  const _MoreButtons({required this.remaining});

  final int remaining;

  @override
  ConsumerState<_MoreButtons> createState() => _MoreButtonsState();
}

class _MoreButtonsState extends ConsumerState<_MoreButtons> {
  bool _loading = false;

  Future<void> _load({required bool all}) async {
    setState(() => _loading = true);
    try {
      await ref.read(localSearchProvider.notifier).loadMore(all: all);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(describeError(e))));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final next = widget.remaining < LocalSearchNotifier.pageSize
        ? widget.remaining
        : LocalSearchNotifier.pageSize;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
      child: Center(
        child: _loading
            ? const Padding(
                padding: EdgeInsets.all(8),
                child: CircularProgressIndicator(strokeWidth: 2))
            : Wrap(
                spacing: 12,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  FilledButton.icon(
                    icon: const Icon(Icons.expand_more, size: 18),
                    label: Text('Show $next more'),
                    onPressed: () => _load(all: false),
                  ),
                  if (widget.remaining > next)
                    OutlinedButton(
                      onPressed: () => _load(all: true),
                      child: Text(
                          'Show all (${widget.remaining} left)'),
                    ),
                ],
              ),
      ),
    );
  }
}

/// M7's note (city relaxed, colour missing, sold out…), styled like the prototype's info blocks.
class _NoteCard extends StatelessWidget {
  const _NoteCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: DmColors.warningBg,
        borderRadius: BorderRadius.circular(DmRadius.card),
        border: Border.all(color: const Color(0xFFE8D1B2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, size: 18, color: DmColors.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text,
                style: DmText.body.copyWith(color: const Color(0xFF6E5540))),
          ),
        ],
      ),
    );
  }
}

/// Product card of the prototype's "Local" tab: photo with a match badge, name, shop · city, price.
class _ProductCard extends ConsumerWidget {
  const _ProductCard({required this.product, this.searchId, this.rank});

  final LocalProduct product;
  final String? searchId;
  final int? rank;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.watch(localMarketRepositoryProvider);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          repo.logEvent('product_view', product,
              searchId: searchId, rank: rank);
          showModalBottomSheet<void>(
            context: context,
            isScrollControlled: true,
            showDragHandle: true,
            builder: (_) => _ProductSheet(
              product: product,
              photoUrl: repo.photoUrl(product),
              onShopLink: () => repo.logEvent('shop_click', product,
                  searchId: searchId, rank: rank),
            ),
          );
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  _Photo(url: repo.photoUrl(product)),
                  Positioned(
                    right: 8,
                    top: 8,
                    child: DmPill('${(product.match * 100).round()} %',
                        dark: true),
                  ),
                  if (!product.available)
                    const Positioned(
                      left: 8,
                      bottom: 8,
                      child: _StockBadge(),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(product.item,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: DmText.itemName),
                  const SizedBox(height: 2),
                  Text(
                    [
                      product.shop,
                      if (product.area != null) shortArea(product.area!)
                    ].join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: DmText.caption,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    product.priceTnd == null
                        ? 'Price?'
                        : formatTnd(product.priceTnd!),
                    style: DmText.price,
                  ),
                  if (product.isLocalBrand) ...[
                    const SizedBox(height: 8),
                    const Divider(height: 1),
                    const SizedBox(height: 6),
                    const Text('Tunisian brand',
                        style: TextStyle(fontSize: 9, color: DmColors.muted)),
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

class _StockBadge extends StatelessWidget {
  const _StockBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(DmRadius.pill),
      ),
      child: const Text('Sold out',
          style: TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w700,
              color: DmColors.warning)),
    );
  }
}

class _Photo extends StatelessWidget {
  const _Photo({required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: DmColors.sand,
      child: Image.network(
        url,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => const Center(
            child: Icon(Icons.image_not_supported_outlined,
                color: DmColors.muted)),
        loadingBuilder: (_, child, progress) => progress == null
            ? child
            : const Center(child: CircularProgressIndicator(strokeWidth: 2)),
      ),
    );
  }
}

class _ProductSheet extends StatelessWidget {
  const _ProductSheet(
      {required this.product, required this.photoUrl, this.onShopLink});

  final LocalProduct product;
  final String photoUrl;

  /// Called when the user takes the shop's link (logged as a shop click for M14).
  final VoidCallback? onShopLink;

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (_, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(DmRadius.panel),
            child: AspectRatio(aspectRatio: 1, child: _Photo(url: photoUrl)),
          ),
          const SizedBox(height: 16),
          Text(
            [product.shop, if (product.area != null) product.area!]
                .join(' · ')
                .toUpperCase(),
            style: DmText.eyebrow,
          ),
          const SizedBox(height: 4),
          Text(product.item, style: DmText.title.copyWith(fontSize: 26)),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              DmPill(product.priceTnd == null
                  ? 'Price?'
                  : formatTnd(product.priceTnd!)),
              DmPill('Match ${(product.match * 100).round()} %'),
              if (product.isLocalBrand) const DmPill('Tunisian brand'),
              if (!product.available) const DmPill('Sold out'),
            ],
          ),
          if (product.size != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: DmColors.surface,
                borderRadius: BorderRadius.circular(DmRadius.small),
                border: Border.all(color: DmColors.border),
              ),
              child: Text('Sizes available: ${product.size}',
                  style: DmText.body),
            ),
          ],
          const SizedBox(height: 20),
          const Text('WHY THIS PIECE', style: DmText.eyebrow),
          const SizedBox(height: 8),
          for (final r in product.reasons)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('◆',
                      style: TextStyle(fontSize: 11, color: DmColors.bar)),
                  const SizedBox(width: 8),
                  Expanded(child: Text(r, style: DmText.body)),
                ],
              ),
            ),
          const SizedBox(height: 12),
          const Text('PRODUCT PAGE', style: DmText.eyebrow),
          const SizedBox(height: 6),
          SelectableText(product.productUrl, style: DmText.caption),
          const SizedBox(height: 16),
          FilledButton.icon(
            icon: const Icon(Icons.open_in_new, size: 18),
            label: const Text("See it on the shop's site"),
            onPressed: () async {
              onShopLink?.call();
              final opened = await launchUrl(Uri.parse(product.productUrl),
                  mode: LaunchMode.externalApplication);
              if (!opened && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                    content: Text('Could not open the site: copy the link')));
              }
            },
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.link, size: 18),
            label: const Text('Copy the link'),
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: product.productUrl));
              if (context.mounted) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(const SnackBar(content: Text('Link copied')));
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
      error: (e, _) =>
          _Message(icon: Icons.cloud_off_outlined, text: describeError(e)),
      data: (list) => ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.only(bottom: 24),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
            child: DmSectionHeader(
                eyebrow: 'Catalogue',
                title: '${list.length} Tunisian shops'),
          ),
          for (final s in list)
            ListTile(
              leading: Container(
                width: 40,
                height: 40,
                decoration: const BoxDecoration(
                    shape: BoxShape.circle, color: DmColors.sandDark),
                child: const Icon(Icons.storefront_outlined,
                    size: 20, color: DmColors.bronzeDark),
              ),
              title: Text(s.shop, style: DmText.itemName),
              subtitle: Text(
                  [s.city ?? 'City not given', s.shopUrl].join(' · '),
                  style: DmText.caption),
              trailing: DmPill('${s.products}'),
            ),
        ],
      ),
    );
  }
}
