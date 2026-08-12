import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../domain/entities/calendar_event.dart';
import '../../../domain/repositories/calendar_repository.dart';
import '../../models/calendar_event_model.dart';

/// Datasource distante : appels HTTP bruts vers `/api/v1/calendar`.
class CalendarRemoteDataSource {
  final Dio _dio;

  const CalendarRemoteDataSource(ApiClient apiClient) : _dio = apiClient.dio;

  Future<List<CalendarEvent>> listEvents({DateTime? startRange, DateTime? endRange}) async {
    final response = await _dio.get('/api/v1/calendar', queryParameters: {
      if (startRange != null) 'start_range': startRange.toIso8601String(),
      if (endRange != null) 'end_range': endRange.toIso8601String(),
    });
    return (response.data as List<dynamic>)
        .map((json) => CalendarEventModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  Future<CreateEventResult> createEvent({
    required String title,
    required DateTime startTime,
    required DateTime endTime,
    required String description,
    required String location,
  }) async {
    final response = await _dio.post(
      '/api/v1/calendar',
      data: CalendarEventModel.toCreateJson(
        title: title,
        startTime: startTime,
        endTime: endTime,
        description: description,
        location: location,
      ),
    );
    return CalendarEventModel.resultFromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteEvent(String eventId) async {
    await _dio.delete('/api/v1/calendar/$eventId');
  }

  Future<bool> isGoogleConnected() async {
    final response = await _dio.get('/api/v1/calendar/connect/status');
    return (response.data as Map<String, dynamic>)['connected'] as bool? ?? false;
  }

  Future<void> connectGoogle(String authorizationCode) async {
    await _dio.post('/api/v1/calendar/connect/callback', data: {'authorization_code': authorizationCode});
  }

  Future<void> disconnectGoogle() async {
    await _dio.delete('/api/v1/calendar/connect');
  }
}
