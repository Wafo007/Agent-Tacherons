import 'package:flutter_test/flutter_test.dart';
import 'package:w4fo_app/domain/entities/task.dart';

void main() {
  group('Task entity', () {
    test('isOverdue renvoie true si dueDate est passée et statut non terminé', () {
      final task = Task(
        id: '1',
        title: 'Test',
        dueDate: DateTime.now().subtract(const Duration(days: 1)),
        status: TaskStatus.todo,
      );
      expect(task.isOverdue, isTrue);
    });

    test('isOverdue renvoie false si la tâche est terminée', () {
      final task = Task(
        id: '1',
        title: 'Test',
        dueDate: DateTime.now().subtract(const Duration(days: 1)),
        status: TaskStatus.done,
      );
      expect(task.isOverdue, isFalse);
    });

    test('copyWith ne modifie que les champs fournis', () {
      const task = Task(id: '1', title: 'Original');
      final updated = task.copyWith(title: 'Modifié');
      expect(updated.title, 'Modifié');
      expect(updated.id, task.id);
      expect(updated.priority, task.priority);
    });

    test('TaskStatusX.apiValue convertit correctement inProgress en snake_case', () {
      expect(TaskStatus.inProgress.apiValue, 'in_progress');
      expect(TaskStatus.todo.apiValue, 'todo');
    });

    test('TaskStatusX.fromApi reconstruit correctement depuis snake_case', () {
      expect(TaskStatusX.fromApi('in_progress'), TaskStatus.inProgress);
      expect(TaskStatusX.fromApi('done'), TaskStatus.done);
    });
  });
}
