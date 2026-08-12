import 'package:equatable/equatable.dart';

/// Entité de domaine : CalendarEvent.
class CalendarEvent extends Equatable {
  final String id;
  final String title;
  final String description;
  final DateTime startTime;
  final DateTime endTime;
  final String location;
  final bool synced;

  const CalendarEvent({
    required this.id,
    required this.title,
    this.description = '',
    required this.startTime,
    required this.endTime,
    this.location = '',
    this.synced = false,
  });

  bool overlapsWith(CalendarEvent other) => startTime.isBefore(other.endTime) && other.startTime.isBefore(endTime);

  @override
  List<Object?> get props => [id, title, description, startTime, endTime, location, synced];
}

/// Conflit détecté par le backend lors de la création d'un événement
/// (voir `CreateEventResponse` côté API).
class CalendarConflict extends Equatable {
  final String id;
  final String title;
  final String startTime;

  const CalendarConflict({required this.id, required this.title, required this.startTime});

  @override
  List<Object?> get props => [id, title, startTime];
}
