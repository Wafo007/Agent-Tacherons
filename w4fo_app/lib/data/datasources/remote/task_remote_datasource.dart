import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../domain/entities/task.dart';
import '../../models/task_model.dart';

/// Datasource distante : appels HTTP bruts vers `/api/v1/tasks`.
class TaskRemoteDataSource {
  final Dio _dio;

  TaskRemoteDataSource(ApiClient apiClient) : _dio = apiClient.dio;

  Future<List<Task>> listTasks({TaskStatus? status, String? category}) async {
    final response = await _dio.get('/api/v1/tasks', queryParameters: {
      if (status != null) 'status_filter': status.apiValue,
      if (category != null) 'category': category,
    });
    return (response.data as List<dynamic>)
        .map((json) => TaskModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<Task> createTask({
    required String title,
    required String description,
    DateTime? dueDate,
    required TaskPriority priority,
    required String category,
  }) async {
    final response = await _dio.post(
      '/api/v1/tasks',
      data: TaskModel.toCreateJson(
        title: title,
        description: description,
        dueDate: dueDate,
        priority: priority,
        category: category,
      ),
    );
    return TaskModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Task> updateTask(String taskId, {String? title, TaskStatus? status, TaskPriority? priority}) async {
    final response = await _dio.patch(
      '/api/v1/tasks/$taskId',
      data: TaskModel.toUpdateJson(title: title, status: status, priority: priority),
    );
    return TaskModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteTask(String taskId) async {
    await _dio.delete('/api/v1/tasks/$taskId');
  }
}
