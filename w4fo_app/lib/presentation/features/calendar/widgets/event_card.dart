import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../domain/entities/calendar_event.dart';

class EventCard extends StatelessWidget {
  final CalendarEvent event;
  final VoidCallback onDelete;

  const EventCard({super.key, required this.event, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final timeFormat = DateFormat.Hm('fr_FR');

    return Dismissible(
      key: ValueKey(event.id),
      direction: DismissDirection.endToStart,
      onDismissed: (_) => onDelete(),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        decoration: BoxDecoration(color: AppColors.danger, borderRadius: BorderRadius.circular(16)),
        child: const Icon(Icons.delete_outline, color: Colors.white),
      ),
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 6),
        child: ListTile(
          leading: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(timeFormat.format(event.startTime), style: const TextStyle(fontWeight: FontWeight.bold)),
              Text(timeFormat.format(event.endTime), style: const TextStyle(color: AppColors.darkOnSurfaceMuted, fontSize: 12)),
            ],
          ),
          title: Text(event.title),
          subtitle: event.location.isNotEmpty ? Text(event.location) : null,
          trailing: event.synced ? const Icon(Icons.cloud_done_outlined, size: 18, color: AppColors.success) : null,
        ),
      ),
    );
  }
}
