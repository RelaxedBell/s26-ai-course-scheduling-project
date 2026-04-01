Technical Proposal


Motivation + Problem Definition
Many students struggle to build their college course schedule during registration season. Some issues we’ve encountered include inconvenient class times, poor professors, boring classes, and insufficient time for transit between classes. Although some students can avoid these issues, it typically takes long hours of researching classes and professors to build a schedule they are satisfied with.

Our goal for our AI model is to recommend a full class schedule that fits students’ specifications and do so much faster than any human can. The inputs to our model include: the student’s current transcript, their preference for the difficulty of the semester, ratings on past courses they’ve taken and professors they’ve had, the number of classes they want to take, the preferred composition of these classes, and time blocks for extracurriculars. The model will first take the transcript, which includes the student's intended degree and past credits, and compile a list of courses that they will need to take in the future. It will then internally generate schedules that satisfy “hard constraints,” like time conflicts and classes needed for the student’s major. Then, once the student gives the “soft preferences” listed above, the model can pick the schedules that progress the student toward graduation while also meeting their preferences.


Methods
Our course recommendation application intends to implement three different AI methods. We will describe the functionality of each of the following AI methods with respect to our project: a Naive Bayes Net, a Neural Network, and a Large Language Model.

We intend to construct a directed acyclic graph representing the courses that a student must take for their degree, as well as preferences for optional classes (perhaps courses outside of one’s major). We then calculate the probability that each potential course will be one that the student likes, likely using a Naive Bayes Net. We set out to answer: “Given what this student likes and what they must complete, how likely is each course to belong in a good schedule?” Importantly, we will assume that course features are conditionally independent given a latent preference profile (information observed from stated preferences) or class. We will then feed these probabilities into a Neural Network (or similar learning model) that organizes the classes into a schedule based on the Bayes Net’s predictions and other constraints. Finally, we will implement a Large Language Model to parse preferences that a user might type into a chatbot, perform sentiment analysis/feature extraction of reviews/course descriptions, and also provide a chain of reasoning for the output we provide.


Data and/or Library
We have three main types of necessary data: course information/reviews, personality to course affinity mappings, and specific course instances/structure.
Course Information/Reviews: These are necessary to get “prior” values for the Bayes Net as well as baseline course attributes. In the absence of more information, we will assume that people enjoy the course in a similar proportion to the reviews we scrape. We plan to use the CourseForum review data either by manually scraping or by directly asking the website operators. CourseForum reviews also provide useful numeric rankings on certain course characteristics (difficulty, instructor rating, etc.). If more data is needed, we can scrape other websites like RateMyProfessor or the UVA subreddit. 

Personality to Course Affinity Mappings: To train the Bayes Net/Neural Network, we will also survey current CS students for their attributes (do you like easy/hard courses, do you like math) and reviews of random courses that they have taken to gain more direct information into relationships between course ratings (since course reviews elsewhere are anonymous and not linked by an identifier). 

Course Instances: We plan to use the university registrar’s website for information on courses, when they are held, and course descriptions. 

Libraries: We can build a graph of course prerequisites with a topological sort via Python’s built-in graphlib. We plan to use pandas for tabular data handling and analysis. For graph data, we can investigate using networkx if graphlib is insufficient. For non-neural network machine learning models (Naive Bayes), we plan to use scikit-learn. If we upgrade to a full-fledged Bayes Net, we might use PyMC. For neural network models, we plan to use PyTorch or TensorFlow. For LLMs, we plan to use open-source models like Qwen (connected to other data via LangChain). This list is not comprehensive, and may be added to as specification changes.


Measure of success
We focus on model evaluation first. We plan to ask users to rate schedules created by the model on a 1-10 scale. This helps in training, but we can also easily make it a useful metric for evaluating model progress. Every once in a while, we can show users a random schedule and ask them to evaluate on a scale of 1-10. If the model is performing significantly better than random, we know that it works (at least somewhat). In an ideal world, we keep versions of our model, and its scores improve over time.

Other measures we can use:
What proportion of users feel more informed about their schedule decisions after using the app?
What proportion of users use the model’s schedule partially/fully?
What is the Net Promoter Score of the application? (How likely are you to recommend this app to a friend/colleague?)
Appendices

A general overview of how this website might work:

