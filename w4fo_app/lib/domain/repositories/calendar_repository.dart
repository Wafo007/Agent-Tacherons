import '../entities/calendar_event.dart';

/// Résultat de la création d'un événement, incluant les conflits détectés côté backend.
class CreateEventResult {
  final String eventId;
  final List<CalendarConflict> conflicts;

  const CreateEventResult({required this.eventId, this.conflicts = const []});
}

/// Interface (Port) : CalendarRepository.
abstract class CalendarRepository {
  Future<List<CalendarEvent>> listEvents({DateTime? startRange, DateTime? endRange});

  Future<CreateEventResult> createEvent({
    required String title,
    required DateTime startTime,
    required DateTime endTime,
    String description = '',
    String location = '',
  });

  Future<void> deleteEvent(String eventId);

  Future<bool> isGoogleConnected();

  Future<void> connectGoogle(String authorizationCode);

  Future<void> disconnectGoogle();
}
