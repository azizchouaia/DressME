// Owner: BO2 (Racem) — save time, as Racem presents it (/bo/screens + /bo/demo): the BO2 agent
// "time_optimisation" and its idea agents (daily_plan, swap, laundry, event_looks, local_shops, declutter),
// each button calling the agent directly.
import 'package:flutter/material.dart';

import '../../bo1_recommendations/ui/racem_agents.dart';

class OutfitOfDayScreen extends StatelessWidget {
  const OutfitOfDayScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const RacemBoPage(
      eyebrow: 'BO2 · Time optimisation',
      title: 'Ready in one tap',
      boAgent: 'time_optimisation',
      sections: [
        AgentSection('Today', 'BO2 · daily_plan', [
          AgentButton('Outfit of the day', 'daily_plan', 'today'),
          AgentButton('Tomorrow', 'daily_plan', 'tomorrow'),
          AgentButton('✓ I take it', 'daily_plan', 'approve'),
          AgentButton('↻ Another', 'daily_plan', 'change'),
          AgentButton('Widget', 'daily_plan', 'widget'),
        ]),
        AgentSection('One tap', 'BO2 · swap', [
          AgentButton('Change shoes', 'swap', 'swap', args: {'slot': 'shoes'}),
          AgentButton('Change top', 'swap', 'swap', args: {'slot': 'top'}),
          AgentButton('Change bottom', 'swap', 'swap', args: {'slot': 'bottom'}),
        ]),
        AgentSection('Laundry', 'BO2 · laundry', [
          AgentButton("What's in the laundry", 'laundry', 'status'),
          AgentButton('Outfit → laundry', 'laundry', 'put', fromOutfit: true),
          AgentButton('Laundry done', 'laundry', 'back'),
        ]),
        AgentSection('Plans', 'BO2', [
          AgentButton('My events', 'event_looks', 'upcoming'),
          AgentButton('Shops: black trousers', 'local_shops', 'find', args: {'query': 'black trousers Tunis 120 TND'}),
          AgentButton('Declutter', 'declutter', 'suggest'),
        ]),
        AgentSection('Cross-BO', 'BO2 agent → BO1 agent', [
          AgentButton('Forgotten pieces (via BO2)', 'personalised_recommendations:forgotten', 'rediscover', viaBo: 'time_optimisation'),
          AgentButton('Event outfit (via BO2)', 'personalised_recommendations:daily_outfit', 'recommend',
              args: {'occasion': 'event'}, viaBo: 'time_optimisation'),
        ], note: 'always sent to the time agent, which asks the recommendations agent'),
      ],
      examples: [
        "What's my outfit for today?", "Tomorrow's outfit", 'Change the shoes', 'My black t-shirt is dirty',
        "What's in the laundry?", 'Laundry is done', 'I have a wedding on 2026-11-07',
        'Where can I buy white sneakers in Tunis under 150 TND?', 'What can I get rid of?', 'My notifications',
      ],
    );
  }
}
