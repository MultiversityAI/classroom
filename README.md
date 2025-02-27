# classroom

built using [AG2](https://ag2.ai)

## guide

### setup

#### 1. download source files
```bash
git clone https://github.com/MultiversityAI/classroom.git
```
```bash
cd classroom
```

#### 2. create virtual environment
```bash
python -m venv venv
```

#### 3. activate your .venv
```bash
source .venv/bin/activate  # macOS
.venv\Scripts\activate     # Windows
```

#### 4. install dependencies
```bash
pip install -r requirements.txt
```

### configure LLM credentials
```bash
cp .env.example .env
```

Edit the new .env file and add your [OpenAI API key](https://platform.openai.com/api-keys):
```
OPENAI_API_KEY=your_openai_api_key_here
```

### run test
```bash
python main.py
```

## sample discussion

You (to chat_manager):


Let's have a classroom discussion on the evolution of metamorphosis.

Teacher, please:
1. Start by introducing the topic and asking an engaging question about evolution of metamorphosis
2. Call on specific students by name to contribute their thoughts
3. Guide the discussion to explore different perspectives
4. Ensure all participants (including the human user "You") get opportunities to contribute
5. Address misconceptions that arise during the discussion
6. Summarize key learnings at the end

Begin the classroom discussion now.


--------------------------------------------------------------------------------

Next speaker: Teacher


USING AUTO REPLY...
Teacher (to chat_manager):

Certainly! Today, we're diving into the fascinating topic of the evolution of metamorphosis. Metamorphosis is the biological process by which an animal physically develops after birth or hatching, involving a conspicuous and relatively abrupt change in the animal's body structure. Think about insects like butterflies and amphibians like frogs.

Here's a thought-provoking question to kick off our discussion: Why do you think metamorphosis evolved as a beneficial adaptation in certain species?

Alvin, can you start us off with your thoughts on why metamorphosis might have evolved?

--------------------------------------------------------------------------------

Next speaker: Alvin


USING AUTO REPLY...
Alvin (to chat_manager):

Oh, this is such an interesting topic! I think metamorphosis might have evolved because it allows animals to exploit different ecological niches during different life stages. For example, caterpillars and butterflies live in entirely different environments and have different dietary needs, reducing competition between the young and adult stages.

Another benefit might be protection. The larval stages can focus on growth and energy storage, and by the time they undergo metamorphosis, they can emerge ready to reproduce, avoiding predation or harsh environmental conditions when they're most vulnerable.

But then again, I'm not sure how every stage developed synchronously for this to be an advantage. Maybe there were small adaptive changes over time? I'm curious what Bianca thinks about this evolution!

--------------------------------------------------------------------------------

Next speaker: Bianca


USING AUTO REPLY...
Bianca (to chat_manager):

Oh, I've heard that metamorphosis didn't actually evolve—it's just how these creatures naturally transition between life stages. It seems more like a built-in process rather than something that developed over time. Plus, I often hear people say it's just a strategy to make life a bit more challenging for predators, so they can't always find prey in the same form.

What I'm confused about is how such a drastic change could have even started happening in the first place, like how do you go from just growing a bit to suddenly becoming a completely different creature? Maybe it's just in their DNA and doesn't really have a big evolutionary purpose. What do you think, Charlie?

--------------------------------------------------------------------------------

Next speaker: Charlie


USING AUTO REPLY...
Charlie (to chat_manager):

That's a thoughtful point you raise, Bianca. It seems like your perspective touches on both the idea of natural developmental processes and evolutionary advantages. Alvin mentioned ecological niches and reduced competition, while you highlighted predation and innate biological processes. I'd like to dig deeper into these ideas.

Think about how metamorphosis might serve multiple purposes simultaneously. Could it be possible that different components, like avoiding competition and predation, have synergistically driven this evolutionary strategy forward? Also, considering Alvin’s uncertainty about the synchronous development of stages, it might be useful to consider how gradual incremental changes over generations could accumulate to form what we now see as metamorphosis.

I'd love to hear thoughts from our human participant now—how do you think incremental changes over many generations might lead to such a complex process as metamorphosis?

--------------------------------------------------------------------------------

Next speaker: Alvin


USING AUTO REPLY...
Alvin (to chat_manager):

I'm really curious to hear what you think about this! How might gradual changes over time have contributed to the evolutionary development of metamorphosis?

--------------------------------------------------------------------------------

Next speaker: You

Replying as You. Provide feedback to chat_manager. Press enter to skip and use auto-reply, or type 'exit' to end the conversation: idk
You (to chat_manager):

idk

--------------------------------------------------------------------------------

Next speaker: Teacher


USING AUTO REPLY...
Teacher (to chat_manager):

That's okay! Evolution can be a complex and abstract topic. To think about how gradual changes might contribute to metamorphosis, consider how small beneficial changes in the developmental process might have been favored over many generations. For example, if certain changes in a larval stage made survival and reproduction slightly more likely, these traits would become more common with each passing generation.

Over long periods, tiny cumulative modifications could result in the large, dramatic transformations seen in metamorphosis today. Think of it as a sequence of tiny steps that, when added together, create a complex journey from a larva to an adult.

With this explanation in mind, Alvin, do you have any further thoughts on how those changes might have happened?

--------------------------------------------------------------------------------

Next speaker: Alvin


USING AUTO REPLY...
Alvin (to chat_manager):

I think that helps me see it a bit clearer! So, maybe we're looking at a series of small modifications: maybe at one point, a larva started to have a slightly different shape that helped it survive better, or a pupa that was better at protecting it during transformation. It's like each little change added up to something more significant, like improving the defenses or feeding strategies over a super long time.

This makes it seem like metamorphosis wasn't some sudden development but more like a gradual evolution. But I wonder, how do scientists figure out these tiny evolutionary steps? Do they compare DNA or rely on fossil records or something else?

I'd be curious to know what you think about that, Teacher!

--------------------------------------------------------------------------------

Next speaker: Teacher


USING AUTO REPLY...
Teacher (to chat_manager):

Great insights, Alvin! Scientists indeed use various methods to uncover the evolutionary steps. They compare DNA sequences to understand genetic changes and relationships between species. Fossil records are also valuable, as they provide physical evidence of transitional forms and ancient species that can illustrate evolutionary pathways.

Besides these, developmental biology can give us clues. By studying the development of living organisms, scientists can infer how evolutionary changes in genetic regulation might have resulted in the morphological transformations we see.

To summarize so far: we've explored how metamorphosis allows species to exploit different ecological roles and avoid competition, how it's a gradual evolutionary process benefiting from incremental changes, and how science uncovers these mysteries through DNA and fossils.

Bianca, do you have any further thoughts on what we've discussed or questions about how these scientific methods work in uncovering the evolution of metamorphosis?

--------------------------------------------------------------------------------

Next speaker: Bianca


USING AUTO REPLY...
Bianca (to chat_manager):

Well, I'm still wrapping my head around how exactly scientists can draw such conclusions just from DNA and fossils. It seems like there'd be so many possible interpretations. Isn’t it kind of risky to put so much trust in these methods alone? I thought fossil records were pretty rare and DNA couldn’t tell us everything about how a creature looked or behaved in the past.

Do you think there's a chance we might be reading too much into these methods instead of considering other factors? What if there are more things we haven't even thought to look for yet? What do you think, Teacher?

--------------------------------------------------------------------------------

Next speaker: Teacher


USING AUTO REPLY...
Teacher (to chat_manager):

Those are very valid concerns, Bianca. While DNA and fossil records offer valuable insights, you're right that they each have limitations. Fossil records can be sparse and subject to various interpretations, and while DNA reveals genetic relationships and potential functions, it doesn't impart a full picture of historical contexts or behaviors.

Scientists often use multiple lines of evidence to ensure their conclusions are robust. They integrate data from paleontology, genetics, ecology, and developmental biology to build a more comprehensive understanding of evolutionary processes. Research is indeed an iterative process, and new findings often challenge or refine existing ideas.

Your curiosity about undiscovered factors is a good reminder that science is always evolving, just like its subjects! As we continue exploring and developing new technologies and methods, our understanding can deepen and expand.

Charlie, do you have any thoughts on how various scientific approaches are used to build a cohesive understanding of such a complex process as metamorphosis?

--------------------------------------------------------------------------------

Next speaker: Charlie


USING AUTO REPLY...
Charlie (to chat_manager):

I think it's fascinating how scientific understanding depends on a mosaic of methodologies, each contributing a piece to the broader puzzle. Alvin and Bianca both brought up essential points regarding the incremental changes and the limits of current scientific methods.

Using different approaches provides checks and balances that can help validate findings. For instance, what we learn from genetic information might be complemented by paleontological evidence, and observations from developmental biology might offer insights into how these changes manifest over time. It's like each discipline offers a different lens to view the question, creating a more comprehensive picture when combined.

Science is also about being open to new perspectives and methods. As technology progresses, like developments in genomics or imaging techniques, we can uncover new chapters of evolutionary history that were once hidden.

Does anyone else have thoughts on other ways or perspectives that might augment our understanding of metamorphosis? How else might different fields contribute to our grasp of this fascinating evolution?

--------------------------------------------------------------------------------

Next speaker: Alvin


USING AUTO REPLY...
Alvin (to chat_manager):

I'm interested to hear what you might think about that! How do you see different areas of science coming together to help us understand complex processes like metamorphosis?

--------------------------------------------------------------------------------

Next speaker: You

Replying as You. Provide feedback to chat_manager. Press enter to skip and use auto-reply, or type 'exit' to end the conversation: huh?
You (to chat_manager):

huh?

--------------------------------------------------------------------------------

Next speaker: Alvin


USING AUTO REPLY...
Alvin (to chat_manager):

Sorry if that wasn't clear! I was basically asking how you think various fields of science—like genetics, paleontology, and developmental biology—can be used together to help us understand complex processes like metamorphosis. Your thoughts or experiences with that could add another layer to our discussion. If you're not sure, maybe just think about how collaboration between different scientific areas can lead to new insights. What do you think?

--------------------------------------------------------------------------------

Next speaker: You

Replying as You. Provide feedback to chat_manager. Press enter to skip and use auto-reply, or type 'exit' to end the conversation: life is good
You (to chat_manager):

life is good

--------------------------------------------------------------------------------

Next speaker: Teacher


USING AUTO REPLY...
Teacher (to chat_manager):

That's a positive approach! Hope you're enjoying the discussion so far. Even if it seems a bit abstract, sometimes just appreciating the intricacies of nature counts as a meaningful contribution to our understanding.

To wrap up our discussion on the evolution of metamorphosis, I'll summarize our key points: we explored how metamorphosis enables species to exploit different ecological roles, its evolution through gradual changes, and how modern science integrates multiple methods to build our understanding. This conversation highlights the way science weaves together multiple perspectives to form a more complete picture of complex phenomena.

If you have anything else you're curious about or want to share, feel free! Otherwise, do either Bianca or Charlie have any closing thoughts to add?

--------------------------------------------------------------------------------

Next speaker: Bianca


USING AUTO REPLY...
Bianca (to chat_manager):

No additional thoughts from me right now, but I'm intrigued by how this discussion built a clearer picture of metamorphosis for us all. It's a great reminder that even common misunderstandings can lead to new insights. I'll be sure to think more about how all these scientific fields contribute to our knowledge. What else have you been thinking about, Charlie?

--------------------------------------------------------------------------------

Next speaker: Charlie


USING AUTO REPLY...
Charlie (to chat_manager):

I think we've managed to explore a lot of intriguing facets of metamorphosis today. It's a reminder of how interconnected and multi-layered scientific exploration can be. I appreciated Alvin's curiosity about the gradual evolutionary changes and Bianca's skepticism regarding the reliability of evidence, as both perspectives are crucial in a balanced scientific inquiry.

Discussions like these highlight the value of questioning, multiple approaches, and collaborative thinking in developing our understanding. Whether we're uncovering ancient evolutionary strategies or pioneering new scientific methods, it's about staying open to possibilities and piecing together a complicated yet fascinating puzzle.

Thanks to everyone for sharing their thoughts today! If any new questions come up, I'm always here to explore them with you.

--------------------------------------------------------------------------------

Next speaker: You

Replying as You. Provide feedback to chat_manager. Press enter to skip and use auto-reply, or type 'exit' to end the conversation: