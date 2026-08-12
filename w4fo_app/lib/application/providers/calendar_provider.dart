import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/injection.dart';
import '../../domain/entities/calendar_event.dart';

class CalendarState {
  final List<CalendarEvent> events;
  final bool isLoading;
  final bool googleConnected;
  final String? errorMessage;
  final List<CalendarConflict> lastConflicts;

  const CalendarState({
    this.events = const [],
    this.isLoading = false,
    this.googleConnected = false,
    this.errorMessage,
    this.lastConflicts = const [],
  });

  CalendarState copyWith({
    List<CalendarEvent>? events,
    bool? isLoading,
    bool? googleConnected,
    String? errorMessage,
    List<CalendarConflict>? lastConflicts,
  }) {
    return CalendarState(
      events: events ?? this.events,
      isLoading: isLoading ?? this.isLoading,
      googleConnected: googleConnected ?? this.googleConnected,
      errorMessage: errorMessage,
      lastConflicts: lastConflicts ?? this.lastConflicts,
    );
  }
}

class CalendarNotifier extends StateNotifier<CalendarState> {
  final Ref _ref;

  CalendarNotifier(this._ref) : super(const CalendarState()) {
    _init();
  }

  Future<void> _init() async {
    await Future.wait([loadEvents(), _checkGoogleConnection()]);
  }

  Future<void> _checkGoogleConnection() async {
    final connected = await _ref.read(calendarRepositoryProvider).isGoogleConnected();
    state = state.copyWith(googleConnected: connected);
  }

  Future<void> loadEvents() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final events = await _ref.read(calendarRepositoryProvider).listEvents();
      state = state.copyWith(events: events, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false, errorMessage: "Impossible de charger l'agenda.");
    }
  }

  /// Crée un événement. Les conflits éventuels détectés côté backend sont
  /// exposés via `lastConflicts` — à l'écran d'afficher une alerte non
  /// bloquante (la création n'est jamais annulée automatiquement, voir §6 du
  /// document d'architecture : notifier plutôt que bloquer).
  Future<void> createEvent({
    required String title,
    required DateTime startTime,
    required DateTime endTime,
    String description = '',
    String location = '',
  }) async {
    try {
      final result = await _ref.read(calendarRepositoryProvider).createEvent(
            title: title,
            startTime: startTime,
            endTime: endTime,
            description: description,
            location: location,
          );
      state = state.copyWith(lastConflicts: result.conflicts);
      await loadEvents();
    } catch (_) {
      state = state.copyWith(errorMessage: "Impossible de créer l'événement.");
    }
  }

  Future<void> deleteEvent(String eventId) async {
    final previousEvents = state.events;
    state = state.copyWith(events: state.events.where((e) => e.id != eventId).toList());
    try {
      await _ref.read(calendarRepositoryProvider).deleteEvent(eventId);
    } catch (_) {
      state = state.copyWith(events: previousEvents, errorMessage: "Impossible de supprimer l'événement.");
    }
  }

  Future<void> connectGoogle(String authorizationCode) async {
    await _ref.read(calendarRepositoryProvider).connectGoogle(authorizationCode);
    state = state.copyWith(googleConnected: true);
    await loadEvents();
  }

  Future<void> disconnectGoogle() async {
    await _ref.read(calendarRepositoryProvider).disconnectGoogle();
    state = state.copyWith(googleConnected: false);
  }
}

final calendarProvider = StateNotifierProvider<CalendarNotifier, CalendarState>((ref) => CalendarNotifier(ref));
