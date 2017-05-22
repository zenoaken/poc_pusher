import pusher

pusher_client = pusher.Pusher(
  app_id='341057',
  key='ab8cf6e917558807f315',
  secret='7d9f17ff32a4d4b2a773',
  cluster='eu',
  ssl=True
)

pusher_client.trigger('my-channel', 'my-event', {'message': 'hello world'})