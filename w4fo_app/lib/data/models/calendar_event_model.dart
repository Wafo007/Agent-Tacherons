import '../../domain/entities/calendar_event.dart';
import '../../domain/repositories/calendar_repository.dart';

class CalendarEventModel {
  static CalendarEvent fromJson(Map<String, dynamic> json) {
    return CalendarEvent(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      startTime: DateTime.parse(json['start_time'] as String),
      endTime: DateTime.parse(json['end_time'] as String),
      location: json['location'] as String? ?? '',
      synced: json['synced'] as bool? ?? false,
    );
  }

  static Map<String, dynamic> toCreateJson({
    required String title,
    required DateTime startTime,
    required DateTime endTime,
    required String description,
    required String location,
  }) {
    return {
      'title': title,
      'start_time': startTime.toIso8601String(),
      'end_time': endTime.toIso8601String(),
      'description': description,
      'location': location,
    };
  }

  static CreateEventResult resultFromJson(Map<String, dynamic> json) {
    final conflictsJson = (json['conflicts'] as List<dynamic>? ?? []);
    return CreateEventResult(
      eventId: json['event_id'] as String,
      conflicts: conflictsJson
          .map((c) => CalendarConflict(
                id: c['id'] as String,
                title: c['title'] as String,
                startTime: c['start_time'] as String,
              ))
          .toList(),
    );
  }
}
