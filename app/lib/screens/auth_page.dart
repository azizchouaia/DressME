import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets/ui.dart';

class AuthPage extends ConsumerStatefulWidget {
  const AuthPage({super.key, required this.register});

  final bool register;

  @override
  ConsumerState<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends ConsumerState<AuthPage> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  var _submitting = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final session = widget.register
          ? await api.register(email: _email.text.trim(), password: _password.text, displayName: _name.text.trim())
          : await api.login(email: _email.text.trim(), password: _password.text);
      await ref.read(authProvider.notifier).setSession(session);
      if (mounted) context.go('/home');
    } catch (error) {
      setState(() {
        _error = error.toString();
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final register = widget.register;
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          child: ListView(
            children: [
              PageHeader(
                showBack: true,
                title: register ? 'Create your wardrobe' : 'Welcome back',
                subtitle: register
                    ? 'We’ll start you with a few sample pieces to try on.'
                    : 'Sign in to see your wardrobe and outfits.',
              ),
              if (register) ...[
                TextField(
                  controller: _name,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'First name'),
                ),
                const SizedBox(height: 12),
              ],
              TextField(
                controller: _email,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'Email'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _password,
                obscureText: true,
                decoration: InputDecoration(
                  labelText: 'Password',
                  helperText: register ? 'At least 8 characters' : null,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: danger)),
              ],
              const SizedBox(height: 16),
              PrimaryButton(
                label: register ? 'Create account' : 'Sign in',
                busy: _submitting,
                onPressed: _submit,
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => context.go(register ? '/login' : '/register'),
                child: Text(register ? 'Already have an account? Sign in' : 'New here? Create an account'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
