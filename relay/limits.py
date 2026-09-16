"""Cap streamed/chunked uploads before the multipart parser consumes the body."""
class BodyLimit:
    def __init__(self,app,limit=151*1024*1024):
        self.app,self.limit=app,limit

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] in ('GET','HEAD','OPTIONS'):
            return await self.app(scope,receive,send)
        total=0
        async def bounded():
            nonlocal total
            message=await receive()
            total+=len(message.get('body',b''))
            if total>self.limit:
                from starlette.exceptions import HTTPException
                raise HTTPException(413,'一次上傳總量不可超過 150 MB')
            return message
        await self.app(scope,bounded,send)
