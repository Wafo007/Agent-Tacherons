import '../../domain/entities/user.dart';

class UserModel {
  static User fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      email: json['email'] as String,
      fullName: json['full_name'] as String,
      timezone: json['timezone'] as String? ?? 'Europe/Paris',
    );
  }
}
