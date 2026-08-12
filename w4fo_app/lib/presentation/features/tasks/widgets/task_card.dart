import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../domain/entities/task.dart';

class TaskCard extends StatelessWidget {
  final Task task;
  final VoidCallback onMarkDone;
  final VoidCallback onDelete;

  const TaskCard({super.key, required this.task, required this.onMarkDone, required this.onDelete});

  Color _priorityColor() {
    switch (task.priority) {
      case TaskPriority.urgent:
        return AppColors.danger;
      case TaskPriority.high:
        return AppColors.warning;
      case TaskPriority.medium:
        return AppColors.primary;
      case TaskPriority.low:
        return AppColors.darkOnSurfaceMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDone = task.status == TaskStatus.done;

    return Dismissible(
      key: ValueKey(task.id),
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
          leading: Checkbox(value: isDone, onChanged: (_) => onMarkDone(), shape: const CircleBorder()),
          title: Text(
            task.title,
            style: TextStyle(decoration: isDone ? TextDecoration.lineThrough : null),
          ),
          subtitle: task.dueDate != null
              ? Text(
                  '${task.dueDate!.day}/${task.dueDate!.month} · ${task.category}',
                  style: TextStyle(color: task.isOverdue ? AppColors.danger : AppColors.darkOnSurfaceMuted),
                )
              : Text(task.category, style: const TextStyle(color: AppColors.darkOnSurfaceMuted)),
          trailing: Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: _priorityColor(), shape: BoxShape.circle),
          ),
        ),
      ),
    );
  }
}
