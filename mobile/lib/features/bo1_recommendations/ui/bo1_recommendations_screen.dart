// Owner: BO1 (Racem) — personalised recommendations, as Racem presents them (/bo/screens + /bo/demo):
// the BO1 agent "personalised_recommendations" and its idea agents (daily_outfit, forgotten, rotation,
// capsule, style_insights, gap_filling, travel), each button calling the agent directly.
import 'package:flutter/material.dart';

import 'racem_agents.dart';

class RecommendationsScreen extends StatelessWidget {
  const RecommendationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const RacemBoPage(
      eyebrow: 'BO1 · Personalised recommendations',
      title: 'Outfits for you',
      boAgent: 'personalised_recommendations',
      sections: [
        AgentSection('Outfit', 'BO1 · daily_outfit', [
          AgentButton('Work outfit', 'daily_outfit', 'recommend', args: {'occasion': 'work'}),
          AgentButton('Casual outfit', 'daily_outfit', 'recommend', args: {'occasion': 'casual'}),
          AgentButton('Remix', 'daily_outfit', 'remix'),
          AgentButton('Why this outfit?', 'daily_outfit', 'why'),
        ]),
        AgentSection('My wardrobe', 'BO1', [
          AgentButton('Forgotten pieces', 'forgotten', 'rediscover'),
          AgentButton('Rotation', 'rotation', 'report'),
          AgentButton('Capsule of 8', 'capsule', 'build', args: {'size': 8}),
          AgentButton('My colours', 'style_insights', 'palette'),
          AgentButton("What I'm missing", 'gap_filling', 'suggest'),
        ]),
        AgentSection('Plans', 'BO1', [
          AgentButton('Pack for Paris · 3 days', 'travel', 'plan', args: {'city': 'Paris', 'days': 3}),
        ]),
        AgentSection('Cross-BO', 'BO1 agent → BO2 agent', [
          AgentButton('Laundry (via BO1)', 'time_optimisation:laundry', 'status', viaBo: 'personalised_recommendations'),
        ], note: 'sent to the recommendations agent, which asks the time agent'),
      ],
      examples: [
        'What should I wear tomorrow for work?', 'Why this outfit?', 'Give me another one',
        'Build an outfit with my black t-shirt', "Show me pieces I haven't worn in a long time", 'Make me a capsule of 8 pieces',
        "Je pars à Paris 3 jours, qu'est-ce que je prends ?", 'What are my colours?', 'Is my style changing?',
        'What am I missing in my wardrobe?',
      ],
    );
  }
}
