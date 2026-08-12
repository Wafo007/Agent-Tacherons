import 'package:equatable/equatable.dart';

/// Entité de domaine : User.
class User extends Equatable {
  final String id;
  final String email;
  final String fullName;
  final String timezone;

  const User({required this.id, required this.email, required this.fullName, this.timezone = 'Europe/Paris'});

  @override
  List<Object?> get props => [id, email, fullName, timezone];
}
