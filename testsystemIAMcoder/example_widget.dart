import 'package:flutter/material.dart';
import '../../core/services/plant_lifecycle_service.dart';
import '../../features/plant_catalog/domain/entities/plant_entity.dart';
import '../../core/theme/app_icons.dart';

/// Nouveau widget de test (remplace l'ancienne classe PlantLifecycleWidget)
/// Version factice et plus conséquente pour test de migration
class PlantLifecyclePanel extends StatefulWidget {
  final PlantFreezed plant;
  final DateTime plantingDate;
  final double? initialProgress;
  final VoidCallback? onUpdateLifecycle;

  const PlantLifecyclePanel({
    super.key,
    required this.plant,
    required this.plantingDate,
    this.initialProgress,
    this.onUpdateLifecycle,
  });

  @override
  State<PlantLifecyclePanel> createState() => _PlantLifecyclePanelState();
}

class _PlantLifecyclePanelState extends State<PlantLifecyclePanel> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 6,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _header(context),
            const SizedBox(height: 12),
            _metrics(context),
            const SizedBox(height: 12),
            _timeline(context),
            const SizedBox(height: 12),
            if (widget.onUpdateLifecycle != null) _actionRow(context),
          ],
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(AppIcons.plant, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Plant Lifecycle — IAMcoder Test',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              Text(
                'Planted: ${widget.plantingDate.day}/${widget.plantingDate.month}/${widget.plantingDate.year}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        IconButton(
          icon: Icon(_expanded ? Icons.expand_less : Icons.expand_more),
          onPressed: () => setState(() => _expanded = !_expanded),
        ),
      ],
    );
  }

  Widget _metrics(BuildContext context) {
    final progress = (widget.initialProgress ?? 0.0).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LinearProgressIndicator(value: progress),
        const SizedBox(height: 8),
        Row(
          children: [
            _metricTile('Progress', '${(progress * 100).toInt()}%'),
            const SizedBox(width: 8),
            _metricTile('Stage', 'Germination'),
            const SizedBox(width: 8),
            _metricTile('Health', 'Good'),
          ],
        ),
      ],
    );
  }

  Widget _metricTile(String label, String value) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
        decoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  Widget _timeline(BuildContext context) {
    if (!_expanded) {
      return const SizedBox.shrink();
    }
    final now = DateTime.now();
    final steps = [
      {'label': 'Sowing', 'date': now.subtract(Duration(days: 20))},
      {'label': 'Germination', 'date': now.subtract(Duration(days: 10))},
      {'label': 'Growth', 'date': now.add(Duration(days: 10))},
      {'label': 'Harvest', 'date': now.add(Duration(days: 40))},
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: steps.map((s) {
        final d = s['date'] as DateTime;
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6.0),
          child: Row(
            children: [
              Container(width: 6, height: 6, decoration: BoxDecoration(color: Colors.green, shape: BoxShape.circle)),
              const SizedBox(width: 10),
              Expanded(child: Text('${s['label']} — ${d.day}/${d.month}/${d.year}')),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _actionRow(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: widget.onUpdateLifecycle,
            icon: const Icon(Icons.update),
            label: const Text('Mettre à jour le cycle — IAMcoder (Complex Test)'),
            style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
          ),
        ),
        const SizedBox(width: 12),
        OutlinedButton(
          onPressed: () {},
          child: const Text('Details'),
        ),
      ],
    );
  }
}
