import '../../domain/entities/calendar_event.dart';
import '../../domain/repositories/calendar_repository.dart';
import '../datasources/remote/calendar_remote_datasource.dart';

class CalendarRepositoryImpl implements CalendarRepository {
  final CalendarRemoteDataSource _remoteDataSource;

  const CalendarRepositoryImpl(this._remoteDataSource);

  @override
  Future<List<CalendarEvent>> listEvents({DateTime? startRange, DateTime? endRange}) {
    return _remoteDataSource.listEvents(startRange: startRange, endRange: endRange);
  }

  @override
  Future<CreateEventResult> createEvent({
    required String title,
    required DateTime startTime,
    required DateTime endTime,
    String description = '',
    String location = '',
  }) {
    return _remoteDataSource.createEvent(
      title: title,
      startTime: startTime,
      endTime: endTime,
      description: description,
      location: location,
    );
  }

  @override
  Future<void> deleteEvent(String eventId) => _remoteDataSource.deleteEvent(eventId);

  @override
  Future<bool> isGoogleConnected() => _remoteDataSource.isGoogleConnected();

  @override
  Future<void> connectGoogle(String authorizationCode) => _remoteDataSource.connectGoogle(authorizationCode);

  @override
  Future<void> disconnectGoogle() => _remoteDataSource.disconnectGoogle();
}
